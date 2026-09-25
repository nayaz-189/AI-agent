from pathlib import Path

from knowledge.canonical_query import get_skills
from knowledge.canonical_recorder import record_skill


# ============================================================
# FIND SKILL
# ============================================================

def find_skill(skill_name):

    skills = get_skills()

    for skill in skills:

        if skill["name"] == skill_name:
            return skill

    return None


# ============================================================
# DISPLAY APPROVAL INFORMATION
# ============================================================

def display_skill_for_approval(skill):

    metadata = skill.get("metadata") or {}

    print()
    print("SKILL APPROVAL REQUEST")
    print("==============================")

    print("Name:", skill["name"])
    print("Version:", skill["version"])
    print("Status:", skill["status"])
    print("Risk level:", skill["risk_level"])
    print("Source:", skill["source"])

    print(
        "Permissions:",
        metadata.get(
            "permissions",
            [],
        ),
    )

    print(
        "Test status:",
        metadata.get(
            "test_status",
            "unknown",
        ),
    )

    print(
        "Test ID:",
        metadata.get(
            "test_id",
        ),
    )

    print()
    print(
        "Approval does NOT execute the skill."
    )


# ============================================================
# APPROVE SKILL
# ============================================================

def approve_skill(skill_name):

    skill = find_skill(skill_name)

    if skill is None:
        return {
            "approved": False,
            "reason": "Skill not found.",
        }

    if skill["status"] != "tested":
        return {
            "approved": False,
            "reason": (
                "Only successfully tested skills "
                "can be approved."
            ),
        }

    metadata = skill.get("metadata") or {}

    if metadata.get("test_status") != "passed":
        return {
            "approved": False,
            "reason": (
                "Skill does not have a passing "
                "canonical test record."
            ),
        }

    skill_id = record_skill(
        name=skill["name"],
        description=skill["description"],
        skill_version=skill["version"],
        source=skill["source"],
        status="approved",
        risk_level=skill["risk_level"],
        metadata={
            **metadata,
            "approval": "human",
            "approval_status": "approved",
        },
    )

    return {
        "approved": True,
        "skill_id": skill_id,
        "reason": "Skill approved by human.",
    }


# ============================================================
# INTERACTIVE APPROVAL
# ============================================================

def request_human_approval(skill_name):

    skill = find_skill(skill_name)

    if skill is None:
        print("Skill not found.")
        return False

    display_skill_for_approval(skill)

    if skill["status"] != "tested":
        print()
        print(
            "BLOCKED: Skill must be tested "
            "before approval."
        )
        return False

    print()
    answer = input(
        "Approve this skill? Type YES to approve: "
    )

    if answer.strip() != "YES":

        print()
        print("Skill was NOT approved.")

        return False

    result = approve_skill(
        skill_name
    )

    print()
    print(
        "Approved:",
        result["approved"],
    )

    print(
        "Reason:",
        result["reason"],
    )

    if result["approved"]:

        print(
            "Skill ID:",
            result["skill_id"],
        )

    return result["approved"]


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    request_human_approval(
        "hello_skill"
    )