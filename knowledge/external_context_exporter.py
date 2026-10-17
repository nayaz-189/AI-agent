import json
import re
from datetime import datetime
from pathlib import Path

from knowledge.project_context_builder import (
    build_project_context,
)


# ============================================================
# EXTERNAL AI CONTEXT EXPORTER
# ============================================================
#
# Creates a deliberately limited representation of the project
# for authorized external development AIs.
#
# SECURITY MODEL:
#
# INTERNAL CONTEXT
#       ↓
# explicit allowlist
#       ↓
# secret-pattern scan
#       ↓
# EXTERNAL CONTEXT
#
# This module does NOT expose the complete internal bridge.
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

EXPORT_PATH = (
    EXPORT_DIRECTORY
    / "external_project_context.json"
)

EXPORT_SCHEMA_VERSION = "2.0"


# ============================================================
# SECRET DETECTION
# ============================================================

SENSITIVE_KEYWORDS = {
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "auth_token",
    "access_token",
    "refresh_token",
    "private_key",
    "credential",
    "credentials",
    "recovery_code",
}


SECRET_PATTERNS = [
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        re.IGNORECASE,
    ),

    re.compile(
        r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"
    ),

    re.compile(
        r"\bsk-[A-Za-z0-9_-]{20,}\b"
    ),
]


def key_is_sensitive(key):
    normalized = (
        str(key)
        .strip()
        .lower()
        .replace("-", "_")
    )

    return (
        normalized
        in SENSITIVE_KEYWORDS
    )


def scan_for_sensitive_keys(
    value,
    path="root",
):
    findings = []

    if isinstance(value, dict):

        for key, child in value.items():

            child_path = (
                f"{path}.{key}"
            )

            if key_is_sensitive(key):

                findings.append(
                    {
                        "type":
                            "sensitive_key",

                        "path":
                            child_path,
                    }
                )

            findings.extend(
                scan_for_sensitive_keys(
                    child,
                    child_path,
                )
            )

    elif isinstance(value, list):

        for index, child in enumerate(
            value
        ):

            findings.extend(
                scan_for_sensitive_keys(
                    child,
                    f"{path}[{index}]",
                )
            )

    return findings


def scan_for_secret_patterns(
    value,
):
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        default=str,
    )

    findings = []

    for pattern in SECRET_PATTERNS:

        if pattern.search(
            serialized
        ):

            findings.append(
                {
                    "type":
                        "secret_pattern",

                    "pattern":
                        pattern.pattern,
                }
            )

    return findings


def security_scan(
    external_context,
):
    findings = []
    from knowledge.public_context_schema import valid_public_context
    if not valid_public_context(external_context):
        # Even attacker-controlled key names must not enter diagnostic output.
        return {"safe": False, "findings": [{"type": "invalid_public_context_schema"}]}

    findings.extend(
        scan_for_sensitive_keys(
            external_context
        )
    )

    findings.extend(
        scan_for_secret_patterns(
            external_context
        )
    )

    return {
        "safe":
            len(findings) == 0,

        "findings":
            findings,
    }


# ============================================================
# ALLOWLIST BUILDERS
# ============================================================

def build_repository_view(internal_context):
    repository = internal_context.get("repository", {})
    branch = repository.get("branch")
    commit = repository.get("short_commit", "")
    return {"branch": branch if branch in {"main", "review/day15-privacy-hardening"} else "other",
            "short_commit": commit if isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{7,40}", commit) else None}


def build_project_view(internal_context):
    project = internal_context.get("project_state", {}).get("project", {})
    version, day, status = project.get("version"), project.get("current_day"), project.get("status")
    return {"name": "AI Agent", "version": version if isinstance(version, str) and re.fullmatch(r"[0-9]+\.[0-9]+(?:\.[0-9]+)?", version) else None,
            "current_day": day if type(day) is int and 0 <= day <= 10000 else None,
            "status": status if status in {"development", "completed"} else "unknown"}


def build_architecture_view(internal_context):
    from knowledge.source_indexer import SOURCE_ROOTS
    return {"source_roots": sorted(SOURCE_ROOTS)}


def build_capability_view(internal_context):
    from execution.audit_schema import ACTIONS
    return [{"name": name} for name in sorted(ACTIONS)]


def build_skill_view(internal_context):
    # Arbitrary skill descriptions and canonical runtime records are private.
    return []


def build_source_interface_view(internal_context):
    from knowledge.source_indexer import source_path_allowed
    modules = {}
    for module in internal_context.get("source_index", {}).get("modules", []):
        if not isinstance(module, dict) or not source_path_allowed(module.get("path")):
            continue
        path = module["path"]
        modules[path] = {"path": path, "parse_success": module.get("parse_success") is True,
                         "function_count": len(module.get("functions", [])),
                         "class_count": len(module.get("classes", []))}
    return {"statistics": {"python_files": len(modules)}, "modules": [modules[k] for k in sorted(modules)]}


def build_development_view(internal_context):
    canonical = internal_context.get("canonical_knowledge", {})
    return {key + "_count": len(canonical.get(key, [])) if isinstance(canonical.get(key), list) else 0
            for key in ("decisions", "bugs", "tests", "research_sources", "upgrades")}


# ============================================================
# EXTERNAL CONTEXT
# ============================================================

def build_external_context():
    """
    Build a restricted external-AI context using explicit
    allowlisted views.
    """

    internal = (
        build_project_context()
    )

    external = {
        "schema_version":
            EXPORT_SCHEMA_VERSION,

        "generated_at": (
            datetime.now()
            .astimezone()
            .isoformat()
        ),

        "purpose":
            (
                "Restricted development context for "
                "authorized external AI systems."
            ),

        "security_boundary": {
            "control_authority":
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

        "project":
            build_project_view(
                internal
            ),

        "repository":
            build_repository_view(
                internal
            ),

        "architecture":
            build_architecture_view(
                internal
            ),

        "source_interfaces":
            build_source_interface_view(
                internal
            ),

        "development":
            build_development_view(
                internal
            ),

        "skills":
            build_skill_view(
                internal
            ),

        "capabilities":
            build_capability_view(
                internal
            ),
    }

    return external


# ============================================================
# EXPORT
# ============================================================

def export_external_context():
    """
    Build, security-scan, and save the external context.

    Fail closed:
    if the security scan finds something suspicious,
    nothing is published.
    """

    external = (
        build_external_context()
    )

    scan = security_scan(
        external
    )

    if not scan["safe"]:

        return {
            "exported": False,
            "reason":
                "External context failed security scan.",

            "findings":
                scan["findings"],
        }

    EXPORT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    EXPORT_PATH.write_text(
        json.dumps(
            external,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    return {
        "exported": True,
        "path":
            str(EXPORT_PATH),

        "security_scan":
            scan,
    }


# ============================================================
# DEVELOPMENT TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("EXTERNAL AI CONTEXT EXPORTER")
    print("==============================")

    result = (
        export_external_context()
    )

    print()
    print(
        "Exported:",
        result.get(
            "exported"
        ),
    )

    if result.get(
        "exported"
    ):

        print(
            "Security scan: SAFE"
        )

        print(
            "Output:",
            result.get(
                "path"
            ),
        )

    else:

        print(
            "Security scan: BLOCKED"
        )

        print(
            "Reason:",
            result.get(
                "reason"
            ),
        )

        print(
            "Findings:"
        )

        for finding in result.get(
            "findings",
            [],
        ):
            print(
                finding
            )
