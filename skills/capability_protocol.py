# ============================================================
# AI AGENT CAPABILITY REQUEST PROTOCOL
# ============================================================
#
# Defines the structured message format used by a skill
# subprocess to REQUEST a capability from the trusted parent
# runtime.
#
# IMPORTANT:
#
# A capability request is NOT authorization.
#
# Skill:
#     creates request
#
# Parent runtime:
#     validates request
#     verifies skill identity
#     checks permissions
#     passes through Execution Gate
#
# The skill never receives direct Tool Registry access.
# ============================================================


PROTOCOL_VERSION = "1.0"

MESSAGE_TYPE_CAPABILITY_REQUEST = (
    "capability_request"
)

MAX_CAPABILITY_NAME_LENGTH = 128
MAX_ARGUMENT_COUNT = 32


# ============================================================
# CREATE REQUEST
# ============================================================

def create_capability_request(
    capability,
    arguments=None,
):
    """
    Create a capability request message.

    This function only creates data.
    It does NOT authorize or execute anything.
    """

    if arguments is None:
        arguments = {}

    return {
        "protocol_version":
            PROTOCOL_VERSION,

        "type":
            MESSAGE_TYPE_CAPABILITY_REQUEST,

        "capability":
            capability,

        "arguments":
            arguments,
    }


# ============================================================
# VALIDATE REQUEST
# ============================================================

def validate_capability_request(
    message,
):
    """
    Validate the outer capability request structure.

    This validates the communication protocol only.

    Capability-specific arguments are validated later by
    the Capability Broker and Argument Validator.
    """

    # --------------------------------------------------------
    # MESSAGE MUST BE A DICTIONARY
    # --------------------------------------------------------

    if not isinstance(message, dict):

        return {
            "valid": False,
            "reason": (
                "Capability request must be "
                "a dictionary."
            ),
        }

    # --------------------------------------------------------
    # ONLY THESE TOP-LEVEL FIELDS ARE ALLOWED
    # --------------------------------------------------------

    allowed_fields = {
        "protocol_version",
        "type",
        "capability",
        "arguments",
    }

    unexpected_fields = (
        set(message.keys())
        - allowed_fields
    )

    if unexpected_fields:

        return {
            "valid": False,
            "reason": (
                "Capability request contains "
                "unexpected fields: "
                + ", ".join(
                    sorted(
                        unexpected_fields
                    )
                )
            ),
        }

    # --------------------------------------------------------
    # REQUIRED FIELDS
    # --------------------------------------------------------

    required_fields = {
        "protocol_version",
        "type",
        "capability",
        "arguments",
    }

    missing_fields = (
        required_fields
        - set(message.keys())
    )

    if missing_fields:

        return {
            "valid": False,
            "reason": (
                "Capability request is missing "
                "required fields: "
                + ", ".join(
                    sorted(
                        missing_fields
                    )
                )
            ),
        }

    # --------------------------------------------------------
    # PROTOCOL VERSION
    # --------------------------------------------------------

    if (
        message["protocol_version"]
        != PROTOCOL_VERSION
    ):

        return {
            "valid": False,
            "reason": (
                "Unsupported capability protocol "
                "version."
            ),
        }

    # --------------------------------------------------------
    # MESSAGE TYPE
    # --------------------------------------------------------

    if (
        message["type"]
        != MESSAGE_TYPE_CAPABILITY_REQUEST
    ):

        return {
            "valid": False,
            "reason": (
                "Unsupported capability message "
                "type."
            ),
        }

    # --------------------------------------------------------
    # CAPABILITY NAME
    # --------------------------------------------------------

    capability = message[
        "capability"
    ]

    if not isinstance(
        capability,
        str,
    ):

        return {
            "valid": False,
            "reason": (
                "Capability name must be a string."
            ),
        }

    capability = capability.strip()

    if not capability:

        return {
            "valid": False,
            "reason": (
                "Capability name cannot be empty."
            ),
        }

    if (
        len(capability)
        > MAX_CAPABILITY_NAME_LENGTH
    ):

        return {
            "valid": False,
            "reason": (
                "Capability name exceeds the "
                "maximum allowed length."
            ),
        }

    # --------------------------------------------------------
    # ARGUMENTS
    # --------------------------------------------------------

    arguments = message[
        "arguments"
    ]

    if not isinstance(
        arguments,
        dict,
    ):

        return {
            "valid": False,
            "reason": (
                "Capability arguments must be "
                "a dictionary."
            ),
        }

    if (
        len(arguments)
        > MAX_ARGUMENT_COUNT
    ):

        return {
            "valid": False,
            "reason": (
                "Capability request contains too "
                "many arguments."
            ),
        }

    # --------------------------------------------------------
    # VALID
    # --------------------------------------------------------

    return {
        "valid": True,
        "reason": (
            "Capability request protocol "
            "validation passed."
        ),
        "request": {
            "protocol_version":
                PROTOCOL_VERSION,

            "type":
                MESSAGE_TYPE_CAPABILITY_REQUEST,

            "capability":
                capability,

            "arguments":
                dict(arguments),
        },
    }


# ============================================================
# DEVELOPMENT TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("CAPABILITY PROTOCOL TEST")
    print("==============================")

    # --------------------------------------------------------
    # VALID REQUEST
    # --------------------------------------------------------

    valid_request = (
        create_capability_request(
            capability="open_website",
            arguments={
                "url":
                    "https://example.com"
            },
        )
    )

    print()
    print("VALID REQUEST")
    print(valid_request)

    print()
    print("VALIDATION")
    print(
        validate_capability_request(
            valid_request
        )
    )

    # --------------------------------------------------------
    # MALICIOUS / INVALID REQUEST
    #
    # A skill must not be able to inject permission claims
    # into the protocol message.
    # --------------------------------------------------------

    injected_permission = {
        "protocol_version":
            PROTOCOL_VERSION,

        "type":
            "capability_request",

        "capability":
            "open_website",

        "arguments": {
            "url":
                "https://example.com"
        },

        "permissions": [
            "browser"
        ],
    }

    print()
    print("PERMISSION INJECTION TEST")
    print(
        validate_capability_request(
            injected_permission
        )
    )

    # --------------------------------------------------------
    # INVALID ARGUMENT CONTAINER
    # --------------------------------------------------------

    invalid_arguments = {
        "protocol_version":
            PROTOCOL_VERSION,

        "type":
            "capability_request",

        "capability":
            "open_website",

        "arguments":
            "https://example.com",
    }

    print()
    print("INVALID ARGUMENT TEST")
    print(
        validate_capability_request(
            invalid_arguments
        )
    )