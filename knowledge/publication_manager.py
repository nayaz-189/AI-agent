import hashlib
import json
from knowledge.public_context_schema import load_public_json
from datetime import datetime
from pathlib import Path

from knowledge.external_context_exporter import (
    EXPORT_PATH,
    export_external_context,
)


# ============================================================
# EXTERNAL KNOWLEDGE PUBLICATION MANAGER
# ============================================================
#
# Builds a verified publication package for authorized
# external development AI systems.
#
# This module:
#
# 1. Regenerates the allowlisted external context
# 2. Requires the security scan to pass
# 3. Calculates SHA-256 integrity information
# 4. Creates a publication manifest
# 5. Verifies the resulting package
#
# It DOES NOT:
#
# - commit
# - push
# - expose credentials
# - grant runtime authority
# - modify the agent brain
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

MANIFEST_PATH = (
    EXPORT_DIRECTORY
    / "external_manifest.json"
)

PUBLICATION_SCHEMA_VERSION = "1.0"


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


def write_json(path, data):

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )


def create_publication_package():
    """
    Regenerate and package the safe external AI context.

    Fail closed if external export/security validation fails.
    """

    export_result = (
        export_external_context()
    )

    if not export_result.get(
        "exported",
        False,
    ):

        return {
            "published": False,
            "reason":
                "External context export was blocked.",

            "details":
                export_result,
        }

    if not EXPORT_PATH.exists():

        return {
            "published": False,
            "reason":
                "External context file was not created.",
        }

    context_hash = (
        calculate_sha256(
            EXPORT_PATH
        )
    )

    try:

        context = load_public_json(
            EXPORT_PATH.read_text(
                encoding="utf-8"
            )
        )

    except Exception as error:

        return {
            "published": False,
            "reason":
                (
                    "External context could not be read."
                ),
        }

    from knowledge.external_context_exporter import security_scan
    if security_scan(context)["safe"] is not True:
        return {"published": False, "reason": "External context schema/privacy validation failed."}

    project = context.get(
        "project",
        {},
    )

    repository = context.get(
        "repository",
        {},
    )

    manifest = {
        "schema_version":
            PUBLICATION_SCHEMA_VERSION,

        "generated_at": (
            datetime.now()
            .astimezone()
            .isoformat()
        ),

        "publication_type":
            "restricted_external_ai_context",

        "project": {
            "name":
                project.get("name"),

            "version":
                project.get("version"),

            "current_day":
                project.get(
                    "current_day"
                ),
        },

        "repository": {
            "branch":
                repository.get("branch"),

            "short_commit":
                repository.get(
                    "short_commit"
                ),
        },

        "security": {
            "allowlist_export":
                True,

            "security_scan_passed":
                True,

            "runtime_authority":
                False,

            "tool_execution_authority":
                False,

            "permission_grant_authority":
                False,

            "canonical_memory_write_authority":
                False,

            "self_upgrade_approval_authority":
                False,
        },

        "artifacts": {
            "external_project_context": {
                "path":
                    "external_project_context.json",

                "sha256":
                    context_hash,
            }
        },

        "authority": {
            "role":
                "read_only_development_context",

            "statement":
                (
                    "This publication provides development "
                    "context only. It does not grant authority "
                    "over the running AI Agent."
                ),
        },
    }

    write_json(
        MANIFEST_PATH,
        manifest,
    )

    return {
        "published": True,
        "context_path":
            str(EXPORT_PATH),

        "manifest_path":
            str(MANIFEST_PATH),

        "sha256":
            context_hash,
    }


def verify_publication_package():
    """
    Verify the external context against the publication
    manifest.
    """

    if not EXPORT_PATH.exists():

        return {
            "valid": False,
            "reason":
                "External context does not exist.",
        }

    if not MANIFEST_PATH.exists():

        return {
            "valid": False,
            "reason":
                "External publication manifest does not exist.",
        }

    try:

        manifest = load_public_json(
            MANIFEST_PATH.read_text(
                encoding="utf-8"
            )
        )

    except Exception as error:

        return {
            "valid": False,
            "reason":
                (
                    "Publication manifest could not be read."
                ),
        }

    if not isinstance(manifest, dict) or not isinstance(manifest.get("artifacts"), dict) or not isinstance(manifest["artifacts"].get("external_project_context"), dict):
        return {"valid": False, "reason": "Invalid publication manifest."}

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

    try:
        actual_hash = calculate_sha256(EXPORT_PATH)
    except Exception:
        return {"valid": False, "reason": "External context could not be read."}

    if not expected_hash:

        return {
            "valid": False,
            "reason":
                "Publication manifest has no context hash.",
        }

    if expected_hash != actual_hash:

        return {
            "valid": False,
            "reason":
                "External context integrity check failed.",

        }

    # A matching hash proves consistency, not privacy or publisher identity.
    from knowledge.external_context_exporter import security_scan
    try:
        context = load_public_json(EXPORT_PATH.read_text(encoding="utf-8"))
        safe = security_scan(context)["safe"] is True
    except Exception:
        safe = False
    if not safe:
        return {"valid": False, "reason": "External context schema/privacy validation failed."}
    from knowledge.public_context_schema import valid_public_manifest
    if not valid_public_manifest(manifest, context, actual_hash):
        return {"valid": False, "reason": "Publication manifest schema validation failed."}
    return {
        "valid": True,
        "reason":
            "External publication package is valid.",

        "sha256":
            actual_hash,
    }


if __name__ == "__main__":

    print()
    print("EXTERNAL KNOWLEDGE PUBLICATION")
    print("==============================")

    result = (
        create_publication_package()
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

        raise SystemExit(1)

    print(
        "Context:",
        result.get(
            "context_path"
        ),
    )

    print(
        "Manifest:",
        result.get(
            "manifest_path"
        ),
    )

    print()
    print("VERIFY")

    verification = (
        verify_publication_package()
    )

    print(
        verification
    )

    if not verification.get(
        "valid",
        False,
    ):

        raise SystemExit(1)
