import hashlib
import json
import shutil
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
    """
    Perform a controlled one-way copy of an EXISTING external
    publication package into the dedicated context repository.

    The package is NOT regenerated here.

    No Git commit or push occurs here.
    """

    # --------------------------------------------------------
    # 1. VERIFY EXISTING PUBLICATION PACKAGE
    # --------------------------------------------------------

    verification = (
        verify_publication_package()
    )

    if not verification.get(
        "valid",
        False,
    ):
        return {
            "published": False,
            "reason":
                "Existing publication package integrity "
                "verification failed.",
            "details":
                verification,
        }

    # --------------------------------------------------------
    # 2. VERIFY DESTINATION REPOSITORY
    # --------------------------------------------------------

    repository_check = (
        validate_context_repository()
    )

    if not repository_check.get(
        "valid",
        False,
    ):
        return {
            "published": False,
            "reason":
                repository_check.get(
                    "reason"
                ),
        }

    # --------------------------------------------------------
    # 3. VERIFY SOURCE ALLOWLIST
    # --------------------------------------------------------

    allowlist_check = (
        validate_artifact_allowlist()
    )

    if not allowlist_check.get(
        "valid",
        False,
    ):
        return {
            "published": False,
            "reason":
                allowlist_check.get(
                    "reason"
                ),
            "details":
                allowlist_check,
        }

    # --------------------------------------------------------
    # 4. VERIFY DESTINATION CONTENT
    # --------------------------------------------------------

    destination_check = (
        destination_is_safe()
    )

    if not destination_check.get(
        "safe",
        False,
    ):
        return {
            "published": False,
            "reason":
                destination_check.get(
                    "reason"
                ),
            "details":
                destination_check,
        }

    # --------------------------------------------------------
    # 5. VERIFY SOURCE HASH AGAINST MANIFEST
    # --------------------------------------------------------

    hash_check = (
        verify_context_hash_against_manifest()
    )

    if not hash_check.get(
        "valid",
        False,
    ):
        return {
            "published": False,
            "reason":
                hash_check.get(
                    "reason"
                ),
            "details":
                hash_check,
        }

    source_hash = (
        hash_check["sha256"]
    )

    # --------------------------------------------------------
    # 6. COPY ONLY ALLOWLISTED FILES
    # --------------------------------------------------------

    copied = []

    for filename in sorted(
        ALLOWED_ARTIFACTS
    ):
        source = (
            EXPORT_DIRECTORY
            / filename
        )

        destination = (
            CONTEXT_REPOSITORY
            / filename
        )

        shutil.copy2(
            source,
            destination,
        )

        copied.append(
            filename
        )

    # --------------------------------------------------------
    # 7. VERIFY DESTINATION CONTEXT HASH
    # --------------------------------------------------------

    destination_context = (
        CONTEXT_REPOSITORY
        / "external_project_context.json"
    )

    destination_hash = (
        calculate_sha256(
            destination_context
        )
    )

    if destination_hash != source_hash:
        return {
            "published": False,
            "reason":
                "Destination context failed "
                "post-copy integrity check.",
            "expected":
                source_hash,
            "actual":
                destination_hash,
        }

    # --------------------------------------------------------
    # 8. VERIFY DESTINATION MANIFEST HASH
    # --------------------------------------------------------

    source_manifest = (
        EXPORT_DIRECTORY
        / "external_manifest.json"
    )

    destination_manifest = (
        CONTEXT_REPOSITORY
        / "external_manifest.json"
    )

    source_manifest_hash = (
        calculate_sha256(
            source_manifest
        )
    )

    destination_manifest_hash = (
        calculate_sha256(
            destination_manifest
        )
    )

    if (
        destination_manifest_hash
        != source_manifest_hash
    ):
        return {
            "published": False,
            "reason":
                "Destination manifest failed "
                "post-copy integrity check.",
            "expected":
                source_manifest_hash,
            "actual":
                destination_manifest_hash,
        }

    return {
        "published": True,
        "destination":
            str(CONTEXT_REPOSITORY),
        "copied":
            copied,
        "sha256":
            destination_hash,
        "manifest_sha256":
            destination_manifest_hash,
    }


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