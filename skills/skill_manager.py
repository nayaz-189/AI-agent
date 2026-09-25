import json
from pathlib import Path

from knowledge.canonical_recorder import (
    record_capability,
    record_skill,
)


# ============================================================
# PATHS
# ============================================================

SKILLS_ROOT = Path(__file__).resolve().parent

INSTALLED_DIRECTORY = (
    SKILLS_ROOT / "installed"
)

QUARANTINE_DIRECTORY = (
    SKILLS_ROOT / "quarantine"
)

WORKSPACE_DIRECTORY = (
    SKILLS_ROOT / "workspace"
)


# ============================================================
# MANIFEST RULES
# ============================================================

REQUIRED_FIELDS = {
    "name",
    "version",
    "description",
    "entrypoint",
    "permissions",
    "risk_level",
}


VALID_RISK_LEVELS = {
    "low",
    "medium",
    "high",
    "critical",
}


VALID_PERMISSIONS = {
    "read_files",
    "write_files",
    "network",
    "browser",
    "applications",
    "terminal",
    "system",
}


# ============================================================
# INITIALIZATION
# ============================================================

def initialize_skill_system():
    """
    Ensure that the skill-system directories exist.
    """

    for directory in [
        INSTALLED_DIRECTORY,
        QUARANTINE_DIRECTORY,
        WORKSPACE_DIRECTORY,
    ]:
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    return True


# ============================================================
# MANIFEST LOADING
# ============================================================

def load_manifest(skill_directory):
    """
    Load manifest.json from a skill directory.

    Loading a manifest does not execute skill code.
    """

    skill_directory = Path(
        skill_directory
    )

    manifest_path = (
        skill_directory
        / "manifest.json"
    )

    if not manifest_path.exists():
        return {
            "valid": False,
            "error":
                "manifest.json is missing.",
        }

    if not manifest_path.is_file():
        return {
            "valid": False,
            "error":
                "manifest.json is not a file.",
        }

    try:
        with manifest_path.open(
            "r",
            encoding="utf-8",
        ) as file_handle:
            manifest = json.load(
                file_handle
            )

    except json.JSONDecodeError as error:
        return {
            "valid": False,
            "error":
                "Invalid manifest JSON: "
                f"{error}",
        }

    except OSError as error:
        return {
            "valid": False,
            "error":
                "Could not read manifest: "
                f"{error}",
        }

    if not isinstance(
        manifest,
        dict,
    ):
        return {
            "valid": False,
            "error":
                "Manifest root must be a JSON object.",
        }

    return {
        "valid": True,
        "manifest": manifest,
        "path": str(
            manifest_path
        ),
    }


# ============================================================
# MANIFEST VALIDATION
# ============================================================

def validate_manifest(manifest):
    """
    Validate the structural and permission contract of a
    skill manifest.

    This does not perform source-code security inspection.
    """

    errors = []
    warnings = []

    if not isinstance(
        manifest,
        dict,
    ):
        return {
            "valid": False,
            "errors": [
                "Manifest must be a dictionary."
            ],
            "warnings": [],
        }

    missing_fields = (
        REQUIRED_FIELDS
        - set(
            manifest.keys()
        )
    )

    if missing_fields:
        errors.append(
            "Missing required fields: "
            + ", ".join(
                sorted(
                    missing_fields
                )
            )
        )

    name = manifest.get(
        "name"
    )

    if (
        not isinstance(
            name,
            str,
        )
        or not name.strip()
    ):
        errors.append(
            "Skill name must be "
            "a non-empty string."
        )

    version = manifest.get(
        "version"
    )

    if (
        not isinstance(
            version,
            str,
        )
        or not version.strip()
    ):
        errors.append(
            "Skill version must be "
            "a non-empty string."
        )

    description = manifest.get(
        "description"
    )

    if (
        not isinstance(
            description,
            str,
        )
        or not description.strip()
    ):
        errors.append(
            "Skill description must be "
            "a non-empty string."
        )

    entrypoint = manifest.get(
        "entrypoint"
    )

    if (
        not isinstance(
            entrypoint,
            str,
        )
        or not entrypoint.strip()
    ):
        errors.append(
            "Skill entrypoint must be "
            "a non-empty string."
        )

    permissions = manifest.get(
        "permissions",
        [],
    )

    if not isinstance(
        permissions,
        list,
    ):
        errors.append(
            "permissions must be a list."
        )
        permissions = []

    else:
        invalid_permission_values = [
            permission
            for permission in permissions
            if not isinstance(
                permission,
                str,
            )
        ]

        if invalid_permission_values:
            errors.append(
                "Every permission must be a string."
            )

        else:
            unknown_permissions = (
                set(
                    permissions
                )
                - VALID_PERMISSIONS
            )

            if unknown_permissions:
                errors.append(
                    "Unknown permissions: "
                    + ", ".join(
                        sorted(
                            unknown_permissions
                        )
                    )
                )

    risk_level = manifest.get(
        "risk_level"
    )

    if risk_level not in VALID_RISK_LEVELS:
        errors.append(
            "Invalid risk_level: "
            f"{risk_level}"
        )

    if "terminal" in permissions:
        warnings.append(
            "Skill requests terminal access."
        )

    if "system" in permissions:
        warnings.append(
            "Skill requests system access."
        )

    if "write_files" in permissions:
        warnings.append(
            "Skill can modify files."
        )

    if "network" in permissions:
        warnings.append(
            "Skill can access the network."
        )

    return {
        "valid":
            len(errors) == 0,
        "errors":
            errors,
        "warnings":
            warnings,
    }


# ============================================================
# SKILL INSPECTION
# ============================================================

def inspect_skill(skill_directory):
    """
    Inspect a skill package without executing its code.

    This validates:
    - directory existence
    - manifest loading
    - manifest structure
    - declared entrypoint existence

    Source-code security inspection remains the responsibility
    of security_inspector.py.
    """

    skill_directory = Path(
        skill_directory
    )

    result = {
        "directory":
            str(
                skill_directory
            ),
        "valid":
            False,
        "manifest":
            None,
        "errors":
            [],
        "warnings":
            [],
    }

    if not skill_directory.exists():
        result["errors"].append(
            "Skill directory does not exist."
        )
        return result

    if not skill_directory.is_dir():
        result["errors"].append(
            "Skill path is not a directory."
        )
        return result

    manifest_result = (
        load_manifest(
            skill_directory
        )
    )

    if not manifest_result[
        "valid"
    ]:
        result["errors"].append(
            manifest_result[
                "error"
            ]
        )
        return result

    manifest = (
        manifest_result[
            "manifest"
        ]
    )

    validation = (
        validate_manifest(
            manifest
        )
    )

    result["manifest"] = (
        manifest
    )

    result["errors"] = (
        validation[
            "errors"
        ]
    )

    result["warnings"] = (
        validation[
            "warnings"
        ]
    )

    result["valid"] = (
        validation[
            "valid"
        ]
    )

    entrypoint = (
        manifest.get(
            "entrypoint"
        )
    )

    if (
        isinstance(
            entrypoint,
            str,
        )
        and entrypoint
    ):
        entrypoint_path = (
            skill_directory
            / entrypoint
        )

        if not entrypoint_path.exists():
            result["valid"] = False

            result["errors"].append(
                "Skill entrypoint does "
                "not exist: "
                f"{entrypoint}"
            )

        elif not entrypoint_path.is_file():
            result["valid"] = False

            result["errors"].append(
                "Skill entrypoint is "
                "not a file: "
                f"{entrypoint}"
            )

    return result


# ============================================================
# REGISTER SKILL
# ============================================================

def register_skill(
    skill_directory,
):
    """
    Register a validated skill in canonical knowledge.

    Registration does NOT execute the skill.

    A corresponding capability record is also created so that
    the knowledge system can represent the capability supplied
    by the registered skill.
    """

    inspection = (
        inspect_skill(
            skill_directory
        )
    )

    if not inspection[
        "valid"
    ]:
        return {
            "registered":
                False,
            "reason":
                "Skill validation failed.",
            "inspection":
                inspection,
        }

    manifest = (
        inspection[
            "manifest"
        ]
    )

    resolved_directory = (
        Path(
            skill_directory
        )
        .resolve()
    )

    skill_id = record_skill(
        name=(
            manifest[
                "name"
            ]
        ),
        description=(
            manifest[
                "description"
            ]
        ),
        skill_version=(
            manifest[
                "version"
            ]
        ),
        source=(
            str(
                resolved_directory
            )
        ),
        status="registered",
        risk_level=(
            manifest[
                "risk_level"
            ]
        ),
        metadata={
            "entrypoint":
                manifest[
                    "entrypoint"
                ],
            "permissions":
                manifest[
                    "permissions"
                ],
            "warnings":
                inspection[
                    "warnings"
                ],
        },
    )

    capability_id = (
        record_capability(
            name=(
                "skill:"
                f"{manifest['name']}"
            ),
            description=(
                manifest[
                    "description"
                ]
            ),
            component=(
                "skill_system"
            ),
            source=(
                "skill:"
                f"{manifest['name']}"
            ),
            status=(
                "registered"
            ),
        )
    )

    return {
        "registered":
            True,
        "skill_id":
            skill_id,
        "capability_id":
            capability_id,
        "name":
            manifest[
                "name"
            ],
        "version":
            manifest[
                "version"
            ],
        "status":
            "registered",
        "inspection":
            inspection,
    }


# ============================================================
# DISCOVER WORKSPACE SKILLS
# ============================================================

def discover_workspace_skills():
    """
    Discover and inspect skill packages currently present in
    the workspace directory.

    Discovery does not execute or register the skills.
    """

    initialize_skill_system()

    discovered = []

    for path in sorted(
        WORKSPACE_DIRECTORY.iterdir(),
        key=lambda item: (
            item.name.lower()
        ),
    ):
        if not path.is_dir():
            continue

        discovered.append(
            inspect_skill(
                path
            )
        )

    return discovered


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":
    initialize_skill_system()

    skills = (
        discover_workspace_skills()
    )

    print(
        "Skill Manager initialized."
    )

    print(
        "Workspace skills:",
        len(
            skills
        ),
    )

    for skill in skills:
        print()
        print(
            "-----------------------------"
        )

        print(
            "Directory:",
            skill[
                "directory"
            ],
        )

        print(
            "Valid:",
            skill[
                "valid"
            ],
        )

        manifest = (
            skill.get(
                "manifest"
            )
        )

        if manifest:
            print(
                "Name:",
                manifest.get(
                    "name"
                ),
            )

            print(
                "Version:",
                manifest.get(
                    "version"
                ),
            )

            print(
                "Risk:",
                manifest.get(
                    "risk_level"
                ),
            )

            print(
                "Permissions:",
                manifest.get(
                    "permissions"
                ),
            )

        if skill[
            "errors"
        ]:
            print(
                "Errors:",
                skill[
                    "errors"
                ],
            )

        if skill[
            "warnings"
        ]:
            print(
                "Warnings:",
                skill[
                    "warnings"
                ],
            )