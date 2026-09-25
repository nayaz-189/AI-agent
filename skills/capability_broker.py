from tools.tool_registry import TOOLS

from skills.argument_validator import (
    validate_capability_arguments,
)


# ============================================================
# AI AGENT CAPABILITY BROKER
# ============================================================
#
# Security boundary between skills and AI Agent tools.
#
# Skills do NOT receive direct access to:
#
# - terminal
# - filesystem
# - browser
# - network
# - system controls
#
# Instead:
#
# Skill
#   ↓
# Permission
#   ↓
# Capability Broker
#   ↓
# Registered capability
#   ↓
# Argument validation
#   ↓
# Tool Registry
#
# IMPORTANT:
# This version validates capability requests.
# It does NOT execute tools yet.
# ============================================================


# ============================================================
# PERMISSION -> CAPABILITY MAP
# ============================================================

PERMISSION_CAPABILITIES = {

    "browser": {
        "open_website",
    },

    "network": set(),

    "read_files": set(),

    "write_files": set(),

    "system": set(),

    "terminal": set(),
}


# ============================================================
# PERMISSION HELPERS
# ============================================================

def get_known_permissions():
    """
    Return all permissions known to the capability broker.
    """

    return set(
        PERMISSION_CAPABILITIES.keys()
    )


def is_known_permission(permission):
    """
    Check whether a permission is recognized.
    """

    return (
        permission
        in PERMISSION_CAPABILITIES
    )


def get_capabilities_for_permission(
    permission
):
    """
    Return capabilities authorized by a permission.
    """

    return set(
        PERMISSION_CAPABILITIES.get(
            permission,
            set(),
        )
    )


def permission_allows_capability(
    permission,
    capability,
):
    """
    Check whether one permission authorizes
    one capability.
    """

    allowed = (
        get_capabilities_for_permission(
            permission
        )
    )

    return capability in allowed


# ============================================================
# BROKER INFORMATION
# ============================================================

def get_broker_summary():
    """
    Return a readable summary of broker policy.
    """

    return {
        permission: sorted(
            capabilities
        )
        for permission, capabilities
        in PERMISSION_CAPABILITIES.items()
    }


# ============================================================
# SKILL-SPECIFIC AUTHORIZATION
# ============================================================

def authorize_capability_request(
    skill_name,
    declared_permissions,
    capability,
):
    """
    Decide whether a specific skill may request
    a specific capability.

    This function makes an authorization decision only.

    It does NOT execute anything.
    """

    declared_permissions = set(
        declared_permissions or []
    )

    # --------------------------------------------------------
    # 1. REJECT UNKNOWN PERMISSIONS
    # --------------------------------------------------------

    unknown_permissions = {
        permission
        for permission in declared_permissions
        if not is_known_permission(
            permission
        )
    }

    if unknown_permissions:

        return {
            "authorized": False,
            "skill": skill_name,
            "capability": capability,
            "reason": (
                "Skill contains unknown permissions."
            ),
            "unknown_permissions": sorted(
                unknown_permissions
            ),
        }

    # --------------------------------------------------------
    # 2. FIND AUTHORIZING PERMISSIONS
    # --------------------------------------------------------

    authorizing_permissions = []

    for permission in declared_permissions:

        if permission_allows_capability(
            permission,
            capability,
        ):

            authorizing_permissions.append(
                permission
            )

    # --------------------------------------------------------
    # 3. DENY IF NOTHING AUTHORIZES CAPABILITY
    # --------------------------------------------------------

    if not authorizing_permissions:

        return {
            "authorized": False,
            "skill": skill_name,
            "capability": capability,
            "reason": (
                "Skill does not have a declared "
                "permission that authorizes this capability."
            ),
            "authorizing_permissions": [],
        }

    return {
        "authorized": True,
        "skill": skill_name,
        "capability": capability,
        "reason": (
            "Capability request is authorized "
            "by declared skill permissions."
        ),
        "authorizing_permissions": sorted(
            authorizing_permissions
        ),
    }


# ============================================================
# CENTRAL TOOL REGISTRY LOOKUP
# ============================================================

def get_registered_capability(
    capability
):
    """
    Return tool metadata only if the capability exists
    in the central Tool Registry.
    """

    tool = TOOLS.get(
        capability
    )

    if tool is None:
        return None

    return tool


# ============================================================
# CAPABILITY REQUEST VALIDATION
# ============================================================

def request_capability(
    skill_name,
    declared_permissions,
    capability,
    arguments=None,
):
    """
    Validate a capability request from a skill.

    Validation order:

    1. Permission authorization
    2. Tool Registry existence
    3. Required arguments
    4. Unexpected arguments
    5. Argument value validation
    6. Prepare validated request

    IMPORTANT:

    Passing this function does NOT execute the capability.
    """

    if arguments is None:
        arguments = {}

    # --------------------------------------------------------
    # 1. AUTHORIZE PERMISSION
    # --------------------------------------------------------

    authorization = (
        authorize_capability_request(
            skill_name=skill_name,
            declared_permissions=(
                declared_permissions
            ),
            capability=capability,
        )
    )

    if not authorization[
        "authorized"
    ]:

        return {
            "accepted": False,
            "skill": skill_name,
            "capability": capability,
            "reason": authorization[
                "reason"
            ],
        }

    # --------------------------------------------------------
    # 2. REQUIRE REGISTERED TOOL
    # --------------------------------------------------------

    tool = get_registered_capability(
        capability
    )

    if tool is None:

        return {
            "accepted": False,
            "skill": skill_name,
            "capability": capability,
            "reason": (
                "Capability is not registered "
                "in the central Tool Registry."
            ),
        }

    # --------------------------------------------------------
    # 3. REQUIRED ARGUMENT VALIDATION
    # --------------------------------------------------------

    required_arguments = tool.get(
        "required_arguments",
        [],
    )

    missing_arguments = [
        argument
        for argument in required_arguments
        if argument not in arguments
    ]

    if missing_arguments:

        return {
            "accepted": False,
            "skill": skill_name,
            "capability": capability,
            "reason": (
                "Capability request is missing "
                "required arguments."
            ),
            "missing_arguments": (
                missing_arguments
            ),
        }

    # --------------------------------------------------------
    # 4. REJECT UNEXPECTED ARGUMENTS
    # --------------------------------------------------------

    allowed_arguments = set(
        required_arguments
    )

    provided_arguments = set(
        arguments.keys()
    )

    unexpected_arguments = (
        provided_arguments
        - allowed_arguments
    )

    if unexpected_arguments:

        return {
            "accepted": False,
            "skill": skill_name,
            "capability": capability,
            "reason": (
                "Capability request contains "
                "unexpected arguments."
            ),
            "unexpected_arguments": sorted(
                unexpected_arguments
            ),
        }

    # --------------------------------------------------------
    # 5. VALIDATE ARGUMENT VALUES
    # --------------------------------------------------------

    argument_validation = (
        validate_capability_arguments(
            capability,
            arguments,
        )
    )

    if not argument_validation[
        "valid"
    ]:

        return {
            "accepted": False,
            "skill": skill_name,
            "capability": capability,
            "reason": (
                "Capability argument validation failed: "
                + argument_validation["reason"]
            ),
        }

    # Use normalized/validated arguments returned
    # by the validator.

    validated_arguments = (
        argument_validation.get(
            "arguments",
            arguments,
        )
    )

    # --------------------------------------------------------
    # 6. ACCEPT VALIDATED REQUEST
    # --------------------------------------------------------

    return {
        "accepted": True,
        "skill": skill_name,
        "capability": capability,
        "arguments": validated_arguments,
        "risk": tool.get(
            "risk",
            "unknown",
        ),
        "agent": tool.get(
            "agent"
        ),
        "authorizing_permissions": (
            authorization.get(
                "authorizing_permissions",
                [],
            )
        ),
        "reason": (
            "Capability request passed "
            "broker validation."
        ),
    }


# ============================================================
# DEVELOPMENT TESTS
# ============================================================

if __name__ == "__main__":

    print()
    print(
        "CAPABILITY BROKER REQUEST TEST"
    )
    print(
        "=============================="
    )

    # --------------------------------------------------------
    # TEST 1
    # Correct permission + valid URL
    # --------------------------------------------------------

    allowed = request_capability(
        skill_name="browser_test_skill",
        declared_permissions=[
            "browser"
        ],
        capability="open_website",
        arguments={
            "url": "https://example.com"
        },
    )

    # --------------------------------------------------------
    # TEST 2
    # No browser permission
    # --------------------------------------------------------

    denied = request_capability(
        skill_name="hello_skill",
        declared_permissions=[],
        capability="open_website",
        arguments={
            "url": "https://example.com"
        },
    )

    # --------------------------------------------------------
    # TEST 3
    # Missing required URL
    # --------------------------------------------------------

    missing_argument = (
        request_capability(
            skill_name=(
                "browser_test_skill"
            ),
            declared_permissions=[
                "browser"
            ],
            capability="open_website",
            arguments={},
        )
    )

    # --------------------------------------------------------
    # TEST 4
    # Unexpected argument injection
    # --------------------------------------------------------

    unexpected_argument = (
        request_capability(
            skill_name=(
                "browser_test_skill"
            ),
            declared_permissions=[
                "browser"
            ],
            capability="open_website",
            arguments={
                "url": (
                    "https://example.com"
                ),
                "command": (
                    "should-not-be-accepted"
                ),
            },
        )
    )

    # --------------------------------------------------------
    # TEST 5
    # Unsafe file URL
    # --------------------------------------------------------

    unsafe_url = request_capability(
        skill_name="browser_test_skill",
        declared_permissions=[
            "browser"
        ],
        capability="open_website",
        arguments={
            "url": (
                "file:///C:/Windows/System32"
            )
        },
    )

    # --------------------------------------------------------
    # TEST 6
    # Wrong URL type
    # --------------------------------------------------------

    wrong_url_type = request_capability(
        skill_name="browser_test_skill",
        declared_permissions=[
            "browser"
        ],
        capability="open_website",
        arguments={
            "url": 12345
        },
    )

    # --------------------------------------------------------
    # PRINT RESULTS
    # --------------------------------------------------------

    print()
    print("AUTHORIZED REQUEST")
    print(allowed)

    print()
    print("UNAUTHORIZED REQUEST")
    print(denied)

    print()
    print("MISSING ARGUMENT TEST")
    print(missing_argument)

    print()
    print(
        "UNEXPECTED ARGUMENT TEST"
    )
    print(unexpected_argument)

    print()
    print("UNSAFE URL TEST")
    print(unsafe_url)

    print()
    print("WRONG URL TYPE TEST")
    print(wrong_url_type)