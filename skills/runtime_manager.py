from pathlib import Path

from knowledge.canonical_query import get_skills

from skills.skill_manager import (
    INSTALLED_DIRECTORY,
    inspect_skill,
)

from skills.security_inspector import (
    inspect_skill_security,
)


# ============================================================
# ACTIVE SKILL REGISTRY
# ============================================================

# Runtime-only registry.
#
# A skill appearing here means it has passed activation checks
# for the CURRENT agent process.
#
# This does NOT automatically execute the skill.

ACTIVE_SKILLS = {}


# ============================================================
# FIND CANONICAL SKILL
# ============================================================

def find_canonical_skill(skill_name):

    for skill in get_skills():

        if skill["name"] == skill_name:
            return skill

    return None


# ============================================================
# FIND INSTALLED PACKAGE
# ============================================================

def get_installed_skill_directory(skill_name):

    skill_directory = (
        INSTALLED_DIRECTORY
        / skill_name
    )

    if not skill_directory.exists():
        return None

    if not skill_directory.is_dir():
        return None

    return skill_directory


# ============================================================
# CHECK ACTIVATION ELIGIBILITY
# ============================================================

def check_activation_eligibility(skill_name):

    result = {
        "eligible": False,
        "skill": skill_name,
        "reason": None,
        "canonical": None,
        "manifest": None,
        "security": None,
        "installed_path": None,
    }

    # --------------------------------------------------------
    # 1. CHECK CANONICAL DATABASE
    # --------------------------------------------------------

    canonical = find_canonical_skill(
        skill_name
    )

    if canonical is None:

        result["reason"] = (
            "Skill does not exist in canonical knowledge."
        )

        return result

    result["canonical"] = canonical

    if canonical["status"] != "installed":

        result["reason"] = (
            "Canonical skill status must be "
            "'installed' before activation."
        )

        return result

    # --------------------------------------------------------
    # 2. FIND INSTALLED PACKAGE
    # --------------------------------------------------------

    skill_directory = (
        get_installed_skill_directory(
            skill_name
        )
    )

    if skill_directory is None:

        result["reason"] = (
            "Installed skill package was not found."
        )

        return result

    result["installed_path"] = str(
        skill_directory
    )

    # --------------------------------------------------------
    # 3. VALIDATE INSTALLED PACKAGE
    # --------------------------------------------------------

    inspection = inspect_skill(
        skill_directory
    )

    if not inspection["valid"]:

        result["reason"] = (
            "Installed skill failed structure validation."
        )

        return result

    manifest = inspection["manifest"]

    result["manifest"] = manifest

    # --------------------------------------------------------
    # 4. VERIFY IDENTITY
    # --------------------------------------------------------

    if manifest["name"] != canonical["name"]:

        result["reason"] = (
            "Installed manifest name does not match "
            "canonical identity."
        )

        return result

    if manifest["version"] != canonical["version"]:

        result["reason"] = (
            "Installed manifest version does not match "
            "the approved canonical version."
        )

        return result

    # --------------------------------------------------------
    # 5. SECURITY RECHECK
    # --------------------------------------------------------

    security = inspect_skill_security(
        skill_directory,
        manifest,
    )

    result["security"] = security

    if security["verdict"] == "block":

        result["reason"] = (
            "Installed skill failed runtime "
            "security inspection."
        )

        return result

    # --------------------------------------------------------
    # ELIGIBLE
    # --------------------------------------------------------

    result["eligible"] = True

    result["reason"] = (
        "Skill is eligible for runtime activation."
    )

    return result
# ============================================================
# ACTIVATE SKILL
# ============================================================

def activate_skill(skill_name):
    """
    Activate an installed skill for the current agent process.

    Activation registers the skill in ACTIVE_SKILLS.
    It does NOT execute the skill.
    """

    # Already active
    if skill_name in ACTIVE_SKILLS:

        return {
            "activated": True,
            "already_active": True,
            "skill": skill_name,
            "reason": "Skill is already active.",
        }

    # Re-run all eligibility checks
    eligibility = check_activation_eligibility(
        skill_name
    )

    if not eligibility["eligible"]:

        return {
            "activated": False,
            "already_active": False,
            "skill": skill_name,
            "reason": eligibility["reason"],
        }

    manifest = eligibility["manifest"]
    canonical = eligibility["canonical"]

    # Register runtime information.
    ACTIVE_SKILLS[skill_name] = {
        "name": manifest["name"],
        "version": manifest["version"],
        "description": manifest["description"],
        "entrypoint": manifest["entrypoint"],
        "permissions": list(
            manifest.get(
                "permissions",
                []
            )
        ),
        "risk_level": manifest["risk_level"],
        "installed_path": eligibility[
            "installed_path"
        ],
        "canonical_skill_id": canonical["id"],
    }

    return {
        "activated": True,
        "already_active": False,
        "skill": skill_name,
        "reason": (
            "Skill activated for the current "
            "agent process."
        ),
    }


# ============================================================
# RUNTIME REGISTRY QUERIES
# ============================================================

def is_skill_active(skill_name):

    return skill_name in ACTIVE_SKILLS


def get_active_skill(skill_name):

    return ACTIVE_SKILLS.get(
        skill_name
    )


def get_active_skills():

    return dict(
        ACTIVE_SKILLS
    )


def deactivate_skill(skill_name):

    if skill_name not in ACTIVE_SKILLS:

        return {
            "deactivated": False,
            "reason": "Skill is not active.",
        }

    del ACTIVE_SKILLS[skill_name]

    return {
        "deactivated": True,
        "reason": (
            "Skill removed from the runtime registry."
        ),
    }
# ============================================================
# CONTROLLED SKILL INVOCATION
# ============================================================

# ============================================================
# CONTROLLED SKILL INVOCATION
# ============================================================

def invoke_skill(skill_name, timeout=10):
    """Expose structural diagnostics only; worker payloads are not audit data."""
    from execution.audit_schema import safe_id
    from execution.safe_failure import safe_result, MESSAGES, ErrorCode
    try:
        result = _invoke_skill(skill_name, timeout)
        success = result.get("success") is True
    except Exception:
        result, success = {}, False
    return {"success": success, "skill": safe_id(skill_name),
            "error_code": None if success else ErrorCode.BACKEND_UNAVAILABLE.value,
            "reason": "Skill executed successfully through worker process." if success else MESSAGES[ErrorCode.BACKEND_UNAVAILABLE],
            "result": safe_result(result.get("result")) if success else None}


def _invoke_skill(skill_name, timeout=10):
    """Fail closed before lookup, path resolution or process creation.

    Installed/active metadata is not OS isolation. There is deliberately no
    environment variable, manifest permission or caller flag to enable this.
    """
    from execution.audit_schema import safe_id
    return {"success": False, "skill": safe_id(skill_name), "result": None,
            "error_code": "backend_unavailable",
            "reason": "Skill execution requires an OS-isolated worker."}
if __name__ == "__main__":

    print()
    print("SKILL RUNTIME TEST")
    print("==============================")

    activation = activate_skill(
        "hello_skill"
    )

    print(
        "Activated:",
        activation["activated"],
    )

    if not activation["activated"]:

        print(
            "Activation failed:",
            activation["reason"],
        )

    else:

        execution = invoke_skill(
            "hello_skill"
        )

        print(
            "Executed:",
            execution["success"],
        )

        print(
            "Reason:",
            execution["reason"],
        )

        print(
            "Result:",
            execution["result"],
        )
