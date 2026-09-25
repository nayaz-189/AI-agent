from skills.capability_broker import (
    request_capability,
)

from skills.capability_audit import (
    record_capability_attempt,
)

from skills.runtime_manager import (
    check_activation_eligibility,
    get_active_skill,
    is_skill_active,
)

from tools.tool_registry import (
    execute_tool,
)


# ============================================================
# AI AGENT SKILL EXECUTION GATE
# ============================================================
#
# Trusted execution boundary between an installed/active
# skill and the central Tool Registry.
#
# Every execution attempt is audited.
#
# Flow:
#
# Skill name
#     ↓
# Runtime identity verification
#     ↓
# Trusted installed permissions
#     ↓
# Capability Broker
#     ↓
# Argument validation
#     ↓
# Risk gate
#     ↓
# Tool Registry
#     ↓
# Controlled execution
#     ↓
# Canonical audit record
#
# ============================================================


# ============================================================
# AUDITED RESULT HELPER
# ============================================================

def build_audited_result(
    *,
    executed,
    skill_name,
    capability,
    reason,
    arguments=None,
    risk=None,
    status=None,
    extra=None,
):
    """
    Create a standard execution result and record the
    capability attempt in canonical knowledge.

    Audit failure is reported in the result but does not
    change whether the capability itself executed.
    """

    audit = record_capability_attempt(
        skill_name=skill_name,
        capability=capability,
        executed=executed,
        reason=reason,
        arguments=arguments,
        risk=risk,
        status=status,
    )

    result = {
        "executed": executed,
        "skill": skill_name,
        "capability": capability,
        "reason": reason,
        "audit": audit,
    }

    if arguments is not None:

        result["arguments"] = arguments

    if risk is not None:

        result["risk"] = risk

    if extra:

        result.update(extra)

    return result


# ============================================================
# RESOLVE TRUSTED SKILL IDENTITY
# ============================================================

def resolve_trusted_skill(skill_name):
    """
    Resolve a skill through trusted runtime state.

    The caller cannot supply its own permissions.

    Permissions come from the verified installed manifest.
    """

    # --------------------------------------------------------
    # 1. REQUIRE ACTIVE SKILL
    # --------------------------------------------------------

    if not is_skill_active(skill_name):

        return {
            "trusted": False,
            "skill": skill_name,
            "reason": (
                "Skill is not active in the current "
                "agent process."
            ),
        }

    # --------------------------------------------------------
    # 2. REVALIDATE INSTALLED SKILL
    # --------------------------------------------------------

    eligibility = (
        check_activation_eligibility(
            skill_name
        )
    )

    if not eligibility["eligible"]:

        return {
            "trusted": False,
            "skill": skill_name,
            "reason": (
                "Skill failed runtime eligibility "
                "revalidation: "
                + eligibility["reason"]
            ),
        }

    # --------------------------------------------------------
    # 3. GET ACTIVE RUNTIME RECORD
    # --------------------------------------------------------

    active_skill = get_active_skill(
        skill_name
    )

    if active_skill is None:

        return {
            "trusted": False,
            "skill": skill_name,
            "reason": (
                "Active skill record could not be found."
            ),
        }

    # --------------------------------------------------------
    # 4. GET VERIFIED MANIFEST + CANONICAL RECORD
    # --------------------------------------------------------

    manifest = eligibility[
        "manifest"
    ]

    canonical = eligibility[
        "canonical"
    ]

    # --------------------------------------------------------
    # 5. VERIFY ACTIVE IDENTITY
    # --------------------------------------------------------

    if (
        active_skill["name"]
        != manifest["name"]
    ):

        return {
            "trusted": False,
            "skill": skill_name,
            "reason": (
                "Active skill identity does not match "
                "the verified installed manifest."
            ),
        }

    if (
        active_skill["version"]
        != manifest["version"]
    ):

        return {
            "trusted": False,
            "skill": skill_name,
            "reason": (
                "Active skill version does not match "
                "the verified installed manifest."
            ),
        }

    # --------------------------------------------------------
    # 6. GET TRUSTED PERMISSIONS
    # --------------------------------------------------------

    trusted_permissions = list(
        manifest.get(
            "permissions",
            [],
        )
    )

    return {
        "trusted": True,
        "skill": skill_name,
        "reason": (
            "Skill identity and permissions were "
            "resolved from trusted runtime state."
        ),
        "permissions": trusted_permissions,
        "manifest": manifest,
        "canonical": canonical,
        "active_skill": active_skill,
    }


# ============================================================
# EXECUTE SKILL CAPABILITY
# ============================================================

def execute_skill_capability(
    skill_name,
    capability,
    arguments=None,
):
    """
    Execute a capability on behalf of an active,
    installed and verified skill.

    The caller supplies:

        skill_name
        capability
        arguments

    The caller does NOT supply permissions.
    """

    if arguments is None:
        arguments = {}

    # --------------------------------------------------------
    # 1. RESOLVE TRUSTED SKILL
    # --------------------------------------------------------

    trusted_skill = (
        resolve_trusted_skill(
            skill_name
        )
    )

    if not trusted_skill[
        "trusted"
    ]:

        return build_audited_result(
            executed=False,
            skill_name=skill_name,
            capability=capability,
            reason=trusted_skill[
                "reason"
            ],
            arguments=arguments,
            status="blocked",
        )

    # --------------------------------------------------------
    # 2. GET TRUSTED PERMISSIONS
    # --------------------------------------------------------

    trusted_permissions = (
        trusted_skill[
            "permissions"
        ]
    )

    # --------------------------------------------------------
    # 3. SEND THROUGH CAPABILITY BROKER
    # --------------------------------------------------------

    broker_result = (
        request_capability(
            skill_name=skill_name,
            declared_permissions=(
                trusted_permissions
            ),
            capability=capability,
            arguments=arguments,
        )
    )

    if not broker_result.get(
        "accepted",
        False,
    ):

        return build_audited_result(
            executed=False,
            skill_name=skill_name,
            capability=capability,
            reason=broker_result.get(
                "reason",
                "Capability broker rejected request.",
            ),
            arguments=arguments,
            status="blocked",
            extra={
                "broker_result":
                    broker_result,
            },
        )

    # --------------------------------------------------------
    # 4. USE VALIDATED ARGUMENTS
    # --------------------------------------------------------

    validated_arguments = (
        broker_result.get(
            "arguments",
            {},
        )
    )

    # --------------------------------------------------------
    # 5. RISK GATE
    # --------------------------------------------------------

    risk = broker_result.get(
        "risk",
        "unknown",
    )

    if risk != "low":

        return build_audited_result(
            executed=False,
            skill_name=skill_name,
            capability=capability,
            reason=(
                "Capability execution blocked because "
                "automatic skill execution currently "
                "allows low-risk tools only."
            ),
            arguments=(
                validated_arguments
            ),
            risk=risk,
            status="blocked",
        )

    # --------------------------------------------------------
    # 6. EXECUTE THROUGH CENTRAL TOOL REGISTRY
    # --------------------------------------------------------

    try:

        success = execute_tool(
            capability,
            validated_arguments,
        )

    except Exception as error:

        return build_audited_result(
            executed=False,
            skill_name=skill_name,
            capability=capability,
            reason=(
                "Tool execution failed: "
                f"{error}"
            ),
            arguments=(
                validated_arguments
            ),
            risk=risk,
            status="failed",
        )

    # --------------------------------------------------------
    # 7. VERIFY TOOL RESULT
    # --------------------------------------------------------

    if success is not True:

        return build_audited_result(
            executed=False,
            skill_name=skill_name,
            capability=capability,
            reason=(
                "Tool Registry did not report "
                "successful execution."
            ),
            arguments=(
                validated_arguments
            ),
            risk=risk,
            status="failed",
        )

    # --------------------------------------------------------
    # 8. SUCCESS + AUDIT
    # --------------------------------------------------------

    return build_audited_result(
        executed=True,
        skill_name=skill_name,
        capability=capability,
        reason=(
            "Capability executed through the "
            "trusted skill execution gate."
        ),
        arguments=(
            validated_arguments
        ),
        risk=risk,
        status="executed",
    )


# ============================================================
# DEVELOPMENT TEST
# ============================================================

if __name__ == "__main__":

    from skills.runtime_manager import (
        activate_skill,
    )

    print()
    print("AUDITED EXECUTION GATE TEST")
    print("==============================")

    # --------------------------------------------------------
    # TEST 1
    # Real approved browser skill.
    # Should execute and create an audit event.
    # --------------------------------------------------------

    activation = activate_skill(
        "browser_skill"
    )

    print()
    print("ACTIVATION")
    print(activation)

    if activation["activated"]:

        allowed = (
            execute_skill_capability(
                skill_name=(
                    "browser_skill"
                ),
                capability=(
                    "open_website"
                ),
                arguments={
                    "url":
                        "https://example.com"
                },
            )
        )

        print()
        print("AUTHORIZED EXECUTION")
        print(allowed)

    # --------------------------------------------------------
    # TEST 2
    # hello_skill has no browser permission.
    # Must be blocked and still audited.
    # --------------------------------------------------------

    hello_activation = (
        activate_skill(
            "hello_skill"
        )
    )

    print()
    print("HELLO ACTIVATION")
    print(hello_activation)

    if hello_activation[
        "activated"
    ]:

        blocked = (
            execute_skill_capability(
                skill_name=(
                    "hello_skill"
                ),
                capability=(
                    "open_website"
                ),
                arguments={
                    "url":
                        "https://example.com"
                },
            )
        )

        print()
        print("BLOCKED EXECUTION")
        print(blocked)