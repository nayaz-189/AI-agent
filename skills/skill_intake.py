from pathlib import Path

from skills.skill_manager import (
    inspect_skill,
    register_skill,
)

from skills.security_inspector import (
    inspect_skill_security,
)


# ============================================================
# SKILL INTAKE PIPELINE
# ============================================================

def intake_skill(skill_directory):
    """
    Safely process a skill before it can move toward execution.

    This function does NOT execute the skill.
    """

    skill_directory = Path(skill_directory).resolve()

    result = {
        "accepted": False,
        "stage": None,
        "skill": None,
        "structure": None,
        "security": None,
        "registration": None,
        "reason": None,
    }

    # ========================================================
    # STAGE 1 — STRUCTURE VALIDATION
    # ========================================================

    result["stage"] = "structure_validation"

    structure = inspect_skill(
        skill_directory
    )

    result["structure"] = structure

    if not structure["valid"]:

        result["reason"] = (
            "Skill structure validation failed."
        )

        return result

    manifest = structure["manifest"]

    result["skill"] = manifest["name"]

    # ========================================================
    # STAGE 2 — SECURITY INSPECTION
    # ========================================================

    result["stage"] = "security_inspection"

    security = inspect_skill_security(
        skill_directory,
        manifest,
    )

    result["security"] = security

    if security["verdict"] == "block":

        result["reason"] = (
            "Skill blocked by security inspection."
        )

        return result

    # ========================================================
    # STAGE 3 — CANONICAL REGISTRATION
    # ========================================================

    result["stage"] = "registration"

    registration = register_skill(
        skill_directory
    )

    result["registration"] = registration

    if not registration["registered"]:

        result["reason"] = (
            "Skill could not be registered."
        )

        return result

    # ========================================================
    # SUCCESS
    # ========================================================

    result["accepted"] = True

    result["stage"] = "registered"

    result["reason"] = (
        "Skill passed intake and was registered."
    )

    return result


# ============================================================
# DISPLAY RESULT
# ============================================================

def print_intake_result(result):

    print()
    print("SKILL INTAKE")
    print("==============================")

    print(
        "Skill:",
        result["skill"],
    )

    print(
        "Accepted:",
        result["accepted"],
    )

    print(
        "Final stage:",
        result["stage"],
    )

    print(
        "Reason:",
        result["reason"],
    )

    security = result.get(
        "security"
    )

    if security:

        print(
            "Security verdict:",
            security["verdict"],
        )

        print(
            "Declared permissions:",
            security["declared_permissions"],
        )

        print(
            "Required permissions:",
            security["required_permissions"],
        )

        print(
            "Undeclared permissions:",
            security["undeclared_permissions"],
        )

        print(
            "Dangerous calls:",
            security["dangerous_calls"],
        )

    registration = result.get(
        "registration"
    )

    if (
        registration
        and registration.get(
            "registered"
        )
    ):

        print(
            "Skill ID:",
            registration["skill_id"],
        )


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    hello_skill = (
        Path(__file__).resolve().parent
        / "workspace"
        / "hello_skill"
    )

    intake_result = intake_skill(
        hello_skill
    )

    print_intake_result(
        intake_result
    )