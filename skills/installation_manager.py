import shutil
from pathlib import Path

from knowledge.canonical_query import get_skills
from knowledge.canonical_recorder import record_skill

from skills.skill_manager import (
    INSTALLED_DIRECTORY,
    inspect_skill,
)

from skills.security_inspector import (
    inspect_skill_security,
)


# ============================================================
# FIND CANONICAL SKILL
# ============================================================

def find_skill(skill_name):

    for skill in get_skills():

        if skill["name"] == skill_name:
            return skill

    return None


# ============================================================
# INSTALL SKILL
# ============================================================

def install_skill(skill_name):
    """
    Install an approved skill.

    Installation does NOT activate or execute the skill.
    """

    skill = find_skill(skill_name)

    if skill is None:
        return {
            "installed": False,
            "reason": "Skill not found in canonical knowledge.",
        }

    # --------------------------------------------------------
    # 1. REQUIRE HUMAN APPROVAL
    # --------------------------------------------------------

    if skill["status"] != "approved":
        return {
            "installed": False,
            "reason": (
                "Skill must have status 'approved' "
                "before installation."
            ),
        }

    metadata = skill.get("metadata") or {}

    if metadata.get("approval_status") != "approved":
        return {
            "installed": False,
            "reason": (
                "Canonical human approval record is missing."
            ),
        }

    # --------------------------------------------------------
    # 2. FIND SOURCE
    # --------------------------------------------------------

    source_directory = Path(
        skill["source"]
    ).resolve()

    if not source_directory.exists():
        return {
            "installed": False,
            "reason": "Skill source directory does not exist.",
        }

    # --------------------------------------------------------
    # 3. REVALIDATE SOURCE
    # --------------------------------------------------------

    inspection = inspect_skill(
        source_directory
    )

    if not inspection["valid"]:
        return {
            "installed": False,
            "reason": (
                "Skill failed structure validation "
                "before installation."
            ),
            "inspection": inspection,
        }

    manifest = inspection["manifest"]

    # --------------------------------------------------------
    # 4. CHECK IDENTITY
    # --------------------------------------------------------

    if manifest["name"] != skill["name"]:
        return {
            "installed": False,
            "reason": (
                "Manifest skill name does not match "
                "canonical skill identity."
            ),
        }

    if manifest["version"] != skill["version"]:
        return {
            "installed": False,
            "reason": (
                "Manifest version does not match "
                "the approved canonical version."
            ),
        }

    # --------------------------------------------------------
    # 5. RE-RUN SECURITY INSPECTION
    # --------------------------------------------------------

    security = inspect_skill_security(
        source_directory,
        manifest,
    )

    if security["verdict"] == "block":
        return {
            "installed": False,
            "reason": (
                "Skill failed security inspection "
                "before installation."
            ),
            "security": security,
        }

    # --------------------------------------------------------
    # 6. PREPARE DESTINATION
    # --------------------------------------------------------

    INSTALLED_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination = (
        INSTALLED_DIRECTORY
        / skill["name"]
    )

    if destination.exists():
        return {
            "installed": False,
            "reason": (
                "An installed skill with this name "
                "already exists."
            ),
            "destination": str(destination),
        }

    # --------------------------------------------------------
    # 7. COPY SKILL
    # --------------------------------------------------------

    try:

        shutil.copytree(
            source_directory,
            destination,
        )

    except Exception as error:

        return {
            "installed": False,
            "reason": (
                f"Could not copy skill: {error}"
            ),
        }

    # --------------------------------------------------------
    # 8. VERIFY COPIED SKILL
    # --------------------------------------------------------

    installed_inspection = inspect_skill(
        destination
    )

    if not installed_inspection["valid"]:

        shutil.rmtree(
            destination,
            ignore_errors=True,
        )

        return {
            "installed": False,
            "reason": (
                "Installed copy failed validation. "
                "Copied files were removed."
            ),
        }

    installed_security = inspect_skill_security(
        destination,
        installed_inspection["manifest"],
    )

    if installed_security["verdict"] == "block":

        shutil.rmtree(
            destination,
            ignore_errors=True,
        )

        return {
            "installed": False,
            "reason": (
                "Installed copy failed security "
                "inspection. Copied files were removed."
            ),
        }

    # --------------------------------------------------------
    # 9. UPDATE CANONICAL KNOWLEDGE
    # --------------------------------------------------------

    updated_metadata = {
        **metadata,
        "installed_path": str(destination),
        "installation_status": "installed",
    }

    skill_id = record_skill(
        name=skill["name"],
        description=skill["description"],
        skill_version=skill["version"],
        source=skill["source"],
        status="installed",
        risk_level=skill["risk_level"],
        metadata=updated_metadata,
    )

    return {
        "installed": True,
        "skill_id": skill_id,
        "name": skill["name"],
        "version": skill["version"],
        "destination": str(destination),
        "security_verdict": (
            installed_security["verdict"]
        ),
        "reason": "Skill installed successfully.",
    }


# ============================================================
# DISPLAY RESULT
# ============================================================

def print_installation_result(result):

    print()
    print("SKILL INSTALLATION")
    print("==============================")

    print(
        "Installed:",
        result["installed"],
    )

    print(
        "Reason:",
        result["reason"],
    )

    if result["installed"]:

        print(
            "Skill ID:",
            result["skill_id"],
        )

        print(
            "Name:",
            result["name"],
        )

        print(
            "Version:",
            result["version"],
        )

        print(
            "Destination:",
            result["destination"],
        )

        print(
            "Security verdict:",
            result["security_verdict"],
        )


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    result = install_skill(
        "hello_skill"
    )

    print_installation_result(
        result
    )