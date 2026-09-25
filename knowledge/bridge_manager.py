import hashlib
import json
from datetime import datetime
from pathlib import Path

from knowledge.project_context_builder import (
    save_project_context,
)


# ============================================================
# AI AGENT PROJECT KNOWLEDGE BRIDGE
# ============================================================
#
# Single refresh point for portable project knowledge.
#
# Purpose:
#
# Actual project
#      ↓
# Rebuild authoritative derived context
#      ↓
# Create integrity information
#      ↓
# Produce portable bridge package
#
# The bridge DOES NOT replace:
#
# - source code
# - Git
# - canonical SQLite
#
# It exposes their current derived representation to other
# authorized AI systems.
# ============================================================


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

STORE_DIRECTORY = (
    PROJECT_ROOT
    / "knowledge"
    / "store"
)

BRIDGE_DIRECTORY = (
    PROJECT_ROOT
    / "knowledge"
    / "bridge"
)

BRIDGE_CONTEXT_PATH = (
    BRIDGE_DIRECTORY
    / "project_context.json"
)

BRIDGE_MANIFEST_PATH = (
    BRIDGE_DIRECTORY
    / "manifest.json"
)

BRIDGE_SCHEMA_VERSION = "1.0"


# ============================================================
# HASHING
# ============================================================

def calculate_sha256(path):
    """
    Calculate SHA-256 for a file.

    Used for integrity detection, not authentication.
    """

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


# ============================================================
# WRITE JSON
# ============================================================

def write_json(path, data):
    """
    Write JSON consistently.
    """

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


# ============================================================
# BUILD BRIDGE
# ============================================================

def refresh_knowledge_bridge():
    """
    Refresh the complete portable project knowledge bridge.
    """

    # --------------------------------------------------------
    # 1. REBUILD UNIFIED CONTEXT
    # --------------------------------------------------------

    context = (
        save_project_context()
    )

    # --------------------------------------------------------
    # 2. WRITE PORTABLE BRIDGE COPY
    # --------------------------------------------------------

    write_json(
        BRIDGE_CONTEXT_PATH,
        context,
    )

    # --------------------------------------------------------
    # 3. HASH PORTABLE CONTEXT
    # --------------------------------------------------------

    context_hash = (
        calculate_sha256(
            BRIDGE_CONTEXT_PATH
        )
    )

    # --------------------------------------------------------
    # 4. BUILD MANIFEST
    # --------------------------------------------------------

    repository = context.get(
        "repository",
        {},
    )

    project_state = context.get(
        "project_state",
        {},
    )

    project = project_state.get(
        "project",
        {},
    )

    source_statistics = (
        context.get(
            "source_index",
            {},
        ).get(
            "statistics",
            {},
        )
    )

    knowledge_summary = (
        context.get(
            "canonical_knowledge",
            {},
        ).get(
            "summary",
            {},
        )
    )

    manifest = {
        "schema_version":
            BRIDGE_SCHEMA_VERSION,

        "generated_at": (
            datetime.now()
            .astimezone()
            .isoformat()
        ),

        "project": {
            "name":
                project.get("name"),

            "day":
                project.get(
                    "current_day"
                ),

            "version":
                project.get(
                    "version"
                ),

            "status":
                project.get(
                    "status"
                ),
        },

        "repository": {
            "branch":
                repository.get(
                    "branch"
                ),

            "commit":
                repository.get(
                    "commit"
                ),

            "short_commit":
                repository.get(
                    "short_commit"
                ),

            "remote":
                repository.get(
                    "remote"
                ),
        },

        "source": {
            "python_files":
                source_statistics.get(
                    "python_files"
                ),

            "top_level_functions":
                source_statistics.get(
                    "top_level_functions"
                ),

            "classes":
                source_statistics.get(
                    "classes"
                ),

            "parse_failures":
                source_statistics.get(
                    "parse_failures"
                ),
        },

        "knowledge":
            knowledge_summary,

        "artifacts": {
            "project_context": {
                "path":
                    "project_context.json",

                "sha256":
                    context_hash,
            }
        },

        "authority": {
            "source_code":
                "authoritative",

            "git":
                "authoritative",

            "canonical_database":
                "authoritative",

            "bridge":
                "derived",
        },
    }

    # --------------------------------------------------------
    # 5. SAVE MANIFEST
    # --------------------------------------------------------

    write_json(
        BRIDGE_MANIFEST_PATH,
        manifest,
    )

    return {
        "refreshed": True,
        "context_path":
            str(BRIDGE_CONTEXT_PATH),

        "manifest_path":
            str(BRIDGE_MANIFEST_PATH),

        "context_sha256":
            context_hash,

        "manifest":
            manifest,
    }


# ============================================================
# VERIFY BRIDGE
# ============================================================

def verify_knowledge_bridge():
    """
    Verify that the bridge context matches its manifest hash.
    """

    if not BRIDGE_CONTEXT_PATH.exists():

        return {
            "valid": False,
            "reason":
                "Bridge project context does not exist.",
        }

    if not BRIDGE_MANIFEST_PATH.exists():

        return {
            "valid": False,
            "reason":
                "Bridge manifest does not exist.",
        }

    try:

        manifest = json.loads(
            BRIDGE_MANIFEST_PATH.read_text(
                encoding="utf-8"
            )
        )

    except Exception as error:

        return {
            "valid": False,
            "reason":
                f"Could not read bridge manifest: {error}",
        }

    expected_hash = (
        manifest.get(
            "artifacts",
            {},
        )
        .get(
            "project_context",
            {},
        )
        .get(
            "sha256"
        )
    )

    actual_hash = (
        calculate_sha256(
            BRIDGE_CONTEXT_PATH
        )
    )

    if (
        not expected_hash
        or expected_hash
        != actual_hash
    ):

        return {
            "valid": False,
            "reason":
                "Bridge context integrity verification failed.",
            "expected_sha256":
                expected_hash,
            "actual_sha256":
                actual_hash,
        }

    return {
        "valid": True,
        "reason":
            "Knowledge bridge integrity verification passed.",
        "sha256":
            actual_hash,
    }


# ============================================================
# DEVELOPMENT TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("PROJECT KNOWLEDGE BRIDGE")
    print("==============================")

    result = (
        refresh_knowledge_bridge()
    )

    print()
    print("REFRESH")
    print(
        "Refreshed:",
        result["refreshed"],
    )

    print(
        "Context:",
        result["context_path"],
    )

    print(
        "Manifest:",
        result["manifest_path"],
    )

    print()
    print("VERIFY")

    verification = (
        verify_knowledge_bridge()
    )

    print(verification)

    manifest = result[
        "manifest"
    ]

    print()
    print("PROJECT")
    print(
        manifest["project"]
    )

    print()
    print("REPOSITORY")
    print(
        manifest["repository"]
    )

    print()
    print("SOURCE")
    print(
        manifest["source"]
    )

    print()
    print("KNOWLEDGE")
    print(
        manifest["knowledge"]
    )