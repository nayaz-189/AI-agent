import hashlib
import json
import os
from contextlib import ExitStack
from pathlib import Path

from knowledge.publication_manager import (
    verify_publication_package,
)


# ============================================================
# EXTERNAL CONTEXT REPOSITORY PUBLISHER
# ============================================================
#
# Purpose:
#
# Protected AI-agent repository
#          ↓
# existing verified external publication package
#          ↓
# strict filename allowlist
#          ↓
# separate AI-agent-context repository
#
# SECURITY RULE:
#
# This module is a boundary copier.
#
# It does NOT generate or regenerate publication artifacts.
# The publication package must already exist before this module
# is called.
#
# It may transfer ONLY explicitly allowlisted artifacts.
#
# It does NOT:
#
# - regenerate external context
# - copy source directories
# - copy arbitrary files
# - copy the canonical database
# - copy the internal bridge
# - commit
# - push
# - grant permissions
# - execute external AI actions
#
# ============================================================


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

EXPORT_DIRECTORY = (
    PROJECT_ROOT
    / "knowledge"
    / "exports"
)

CONTEXT_REPOSITORY = Path(
    r"C:\AI-agent-context"
)


ALLOWED_ARTIFACTS = {
    "external_project_context.json",
    "external_manifest.json",
}


def _check_publication_handle(handle, path, *, directory=False):
    import win32file
    info = win32file.GetFileInformationByHandle(handle)
    actual = win32file.GetFinalPathNameByHandle(handle, 0).removeprefix("\\\\?\\")
    if (info[0] & 0x400 or bool(info[0] & 0x10) != directory
            or os.path.normcase(actual) != os.path.normcase(os.path.abspath(path))
            or (not directory and info[7] != 1)):
        raise ValueError("Unsafe publication path.")
    return info


def _lock_publication_directory(stack, directory):
    """Hold ancestors against rename/delete, including junction replacement."""
    import win32con
    import win32file
    for path in reversed((directory, *directory.parents)):
        handle = win32file.CreateFile(str(path), 0x80,
            win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE, None,
            win32con.OPEN_EXISTING, 0x02000000 | 0x00200000, None)
        stack.callback(handle.Close)
        _check_publication_handle(handle, path, directory=True)


def _open_publication_file(stack, path, *, writable=False, readback=False):
    import win32con
    import win32file
    access = win32con.GENERIC_READ | (win32con.GENERIC_WRITE if writable else 0)
    sharing = win32con.FILE_SHARE_READ | (win32con.FILE_SHARE_WRITE if readback else 0)
    handle = win32file.CreateFile(str(path), access, sharing, None,
        win32con.OPEN_ALWAYS if writable else win32con.OPEN_EXISTING,
        win32con.FILE_ATTRIBUTE_NORMAL | 0x00200000, None)
    stack.callback(handle.Close)
    # Validate before reading or truncating, including pre-existing hardlinks.
    _check_publication_handle(handle, path)
    return handle


def _read_publication_handle(handle):
    import win32file
    info = win32file.GetFileInformationByHandle(handle)
    size = (info[5] << 32) | info[6]
    if size > 2_000_000:
        raise ValueError("Publication size limit exceeded.")
    data = win32file.ReadFile(handle, size)[1] if size else b""
    if len(data) != size:
        raise ValueError("Incomplete publication read.")
    return data


def _validate_publication_bytes(artifacts):
    from knowledge.public_context_schema import valid_public_context, valid_public_manifest, load_public_json
    context = load_public_json(artifacts["external_project_context.json"])
    manifest = load_public_json(artifacts["external_manifest.json"])
    digest = hashlib.sha256(artifacts["external_project_context.json"]).hexdigest()
    if not valid_public_context(context) or not valid_public_manifest(manifest, context, digest):
        raise ValueError("Publication schema or integrity validation failed.")
    return digest


def _publish_locked_snapshot():
    """Copy only validated bytes while source/destination identities are held."""
    import win32con
    import win32file
    if os.name != "nt":
        raise RuntimeError("Checked publication is available only on Windows.")
    with ExitStack() as stack:
        _lock_publication_directory(stack, EXPORT_DIRECTORY)
        _lock_publication_directory(stack, CONTEXT_REPOSITORY)
        if (CONTEXT_REPOSITORY.name != "AI-agent-context"
                or not (CONTEXT_REPOSITORY / ".git").is_dir()
                or {p.name for p in EXPORT_DIRECTORY.iterdir()} != ALLOWED_ARTIFACTS
                or {p.name for p in CONTEXT_REPOSITORY.iterdir()} - ALLOWED_ARTIFACTS - {".git"}):
            raise ValueError("Invalid publication directories.")
        sources = {name: _open_publication_file(stack, EXPORT_DIRECTORY / name)
                   for name in sorted(ALLOWED_ARTIFACTS)}
        artifacts = {name: _read_publication_handle(handle) for name, handle in sources.items()}
        digest = _validate_publication_bytes(artifacts)
        destinations = {name: _open_publication_file(stack, CONTEXT_REPOSITORY / name, writable=True)
                        for name in sorted(ALLOWED_ARTIFACTS)}
        for name, handle in destinations.items():
            data = artifacts[name]
            win32file.SetFilePointer(handle, 0, win32con.FILE_BEGIN)
            status, written = win32file.WriteFile(handle, data)
            if status != 0 or written != len(data):
                raise RuntimeError("Incomplete publication write.")
            win32file.SetEndOfFile(handle)
            win32file.FlushFileBuffers(handle)
            reader = _open_publication_file(stack, CONTEXT_REPOSITORY / name, readback=True)
            if _read_publication_handle(reader) != data:
                raise RuntimeError("Publication readback failed.")
        return {"published": True, "destination": str(CONTEXT_REPOSITORY),
                "copied": sorted(ALLOWED_ARTIFACTS), "sha256": digest,
                "manifest_sha256": hashlib.sha256(artifacts["external_manifest.json"]).hexdigest()}


def calculate_sha256(path):
    digest = hashlib.sha256()

    with path.open("rb") as file_handle:
        while True:
            chunk = file_handle.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def validate_context_repository():
    """
    Verify that the destination looks like the dedicated
    context Git repository.
    """

    if not CONTEXT_REPOSITORY.exists():
        return {
            "valid": False,
            "reason":
                "Context repository directory does not exist.",
        }

    git_directory = (
        CONTEXT_REPOSITORY
        / ".git"
    )

    if not git_directory.exists():
        return {
            "valid": False,
            "reason":
                "Destination is not a Git repository.",
        }

    if (
        CONTEXT_REPOSITORY.name
        != "AI-agent-context"
    ):
        return {
            "valid": False,
            "reason":
                "Unexpected context repository directory name.",
        }

    return {
        "valid": True,
    }


def load_publication_manifest():
    manifest_path = (
        EXPORT_DIRECTORY
        / "external_manifest.json"
    )

    if not manifest_path.exists():
        raise RuntimeError(
            "External publication manifest does not exist."
        )

    return json.loads(
        manifest_path.read_text(
            encoding="utf-8"
        )
    )


def validate_artifact_allowlist():
    """
    Ensure that the publication directory contains only files
    explicitly permitted to cross the repository boundary.

    Fail closed if any unexpected file is present.
    """

    if not EXPORT_DIRECTORY.exists():
        return {
            "valid": False,
            "reason":
                "Export directory does not exist.",
        }

    actual_files = {
        path.name
        for path in EXPORT_DIRECTORY.iterdir()
        if path.is_file()
    }

    unexpected = (
        actual_files
        - ALLOWED_ARTIFACTS
    )

    missing = (
        ALLOWED_ARTIFACTS
        - actual_files
    )

    if unexpected:
        return {
            "valid": False,
            "reason":
                "Unexpected files exist in publication directory.",
            "unexpected":
                sorted(unexpected),
        }

    if missing:
        return {
            "valid": False,
            "reason":
                "Required publication artifacts are missing.",
            "missing":
                sorted(missing),
        }

    return {
        "valid": True,
        "files":
            sorted(actual_files),
    }


def verify_context_hash_against_manifest():
    """
    Independently verify the external context hash before it
    crosses the repository boundary.
    """

    manifest = (
        load_publication_manifest()
    )

    context_path = (
        EXPORT_DIRECTORY
        / "external_project_context.json"
    )

    if not context_path.exists():
        return {
            "valid": False,
            "reason":
                "External project context does not exist.",
        }

    expected_hash = (
        manifest.get(
            "artifacts",
            {},
        )
        .get(
            "external_project_context",
            {},
        )
        .get(
            "sha256"
        )
    )

    if not expected_hash:
        return {
            "valid": False,
            "reason":
                "Publication manifest does not contain context hash.",
        }

    actual_hash = (
        calculate_sha256(
            context_path
        )
    )

    if actual_hash != expected_hash:
        return {
            "valid": False,
            "reason":
                "External context hash does not match manifest.",
            "expected":
                expected_hash,
            "actual":
                actual_hash,
        }

    return {
        "valid": True,
        "sha256":
            actual_hash,
    }


def destination_is_safe():
    """
    Refuse publication if unexpected files already exist in
    the context repository.

    .git is the only non-publication entry automatically
    permitted.
    """

    entries = {
        path.name
        for path in CONTEXT_REPOSITORY.iterdir()
        if path.name != ".git"
    }

    unexpected = (
        entries
        - ALLOWED_ARTIFACTS
    )

    if unexpected:
        return {
            "safe": False,
            "reason":
                "Unexpected content exists in context repository.",
            "unexpected":
                sorted(unexpected),
        }

    return {
        "safe": True,
    }


def publish_to_context_repository():
    """Copy a verified snapshot using held Windows handles, without Git writes.

    Failure may leave an incomplete pair inside the approved destination;
    it never reports that pair as successfully published.
    """
    try:
        return _publish_locked_snapshot()
    except Exception:
        return {"published": False, "reason": "Publication was blocked or verification failed."}


if __name__ == "__main__":
    print()
    print("CONTEXT REPOSITORY PUBLISHER")
    print("==============================")

    result = (
        publish_to_context_repository()
    )

    print()

    print(
        "Published:",
        result.get(
            "published"
        ),
    )

    if not result.get(
        "published"
    ):
        print(
            "Reason:",
            result.get(
                "reason"
            ),
        )

        details = result.get(
            "details"
        )

        if details:
            print(
                "Details:",
                details,
            )

        raise SystemExit(1)

    print(
        "Destination:",
        result.get(
            "destination"
        ),
    )

    print(
        "Copied:",
        result.get(
            "copied"
        ),
    )

    print(
        "SHA-256:",
        result.get(
            "sha256"
        ),
    )

    print(
        "Manifest SHA-256:",
        result.get(
            "manifest_sha256"
        ),
    )

    print()

    print(
        "NOTE: Existing publication files "
        "were copied only."
    )

    print(
        "No publication package regeneration "
        "occurred."
    )

    print(
        "No Git commit or push was performed."
    )
