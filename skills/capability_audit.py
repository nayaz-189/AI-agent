from knowledge.canonical_recorder import (
    record_event,
)


# ============================================================
# AI AGENT CAPABILITY AUDIT
# ============================================================
#
# Permanent audit trail for skill capability activity.
#
# Records:
# - skill identity
# - requested capability
# - execution result
# - risk level
# - sanitized arguments
# - reason
#
# IMPORTANT:
# Secrets must never be written directly into canonical
# project knowledge.
# ============================================================


SENSITIVE_ARGUMENT_NAMES = {
    "password",
    "passwd",
    "token",
    "api_key",
    "apikey",
    "secret",
    "authorization",
    "auth_token",
    "access_token",
    "refresh_token",
    "private_key",
    "credential",
    "credentials",
}


# ============================================================
# SENSITIVE KEY DETECTION
# ============================================================

def is_sensitive_key(key):
    """
    Determine whether an argument name is sensitive.
    """

    normalized = (
        str(key)
        .lower()
        .strip()
    )

    return (
        normalized
        in SENSITIVE_ARGUMENT_NAMES
    )


# ============================================================
# RECURSIVE REDACTION
# ============================================================

def redact_value(value):
    """
    Recursively sanitize structured values.
    """

    if isinstance(value, dict):

        cleaned = {}

        for key, nested_value in value.items():

            if is_sensitive_key(key):

                cleaned[key] = "[REDACTED]"

            else:

                cleaned[key] = redact_value(
                    nested_value
                )

        return cleaned

    if isinstance(value, list):

        return [
            redact_value(item)
            for item in value
        ]

    if isinstance(value, tuple):

        return [
            redact_value(item)
            for item in value
        ]

    return value


# ============================================================
# ARGUMENT SANITIZATION
# ============================================================

def sanitize_arguments(arguments):
    """
    Return a safe copy of capability arguments.
    """

    if arguments is None:

        return {}

    if not isinstance(arguments, dict):

        return {
            "_invalid_arguments_type":
                type(arguments).__name__
        }

    return redact_value(
        arguments
    )


# ============================================================
# CAPABILITY AUDIT RECORD
# ============================================================

def record_capability_attempt(
    skill_name,
    capability,
    executed,
    reason,
    arguments=None,
    risk=None,
    status=None,
):
    """
    Record one capability attempt.

    This function NEVER executes a capability.
    """

    safe_arguments = sanitize_arguments(
        arguments
    )

    # Determine audit status automatically unless
    # the caller explicitly provides one.

    if status is None:

        status = (
            "executed"
            if executed
            else "blocked"
        )

    metadata = {
        "skill": skill_name,
        "capability": capability,
        "executed": bool(executed),
        "reason": reason,
        "arguments": safe_arguments,
        "risk": risk,
    }

    description = (
        f"Skill '{skill_name}' requested "
        f"capability '{capability}': "
        f"{status}."
    )

    try:

        event_id = record_event(
            event_type="capability_execution",
            component="skill_system",
            description=description,
            status=status,
            metadata=metadata,
        )

    except Exception as error:

        return {
            "recorded": False,
            "event_id": None,
            "reason": (
                "Capability audit recording failed: "
                f"{error}"
            ),
        }

    return {
        "recorded": True,
        "event_id": event_id,
        "reason": (
            "Capability attempt recorded "
            "in canonical knowledge."
        ),
    }


# ============================================================
# DEVELOPMENT TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("CAPABILITY AUDIT TEST")
    print("==============================")

    # --------------------------------------------------------
    # TEST REDACTION
    # --------------------------------------------------------

    sanitized = sanitize_arguments(
        {
            "url": "https://example.com",

            "token":
                "DO-NOT-STORE-THIS",

            "nested": {
                "password":
                    "SECRET-PASSWORD",

                "safe_value":
                    "hello",
            },
        }
    )

    print()
    print("SANITIZED ARGUMENTS")
    print(sanitized)

    # --------------------------------------------------------
    # TEST CANONICAL RECORDING
    # --------------------------------------------------------

    audit = record_capability_attempt(
        skill_name="audit_test_skill",
        capability="open_website",
        executed=False,
        reason=(
            "Development audit test."
        ),
        arguments={
            "url":
                "https://example.com",

            "api_key":
                "SUPER-SECRET-KEY",
        },
        risk="low",
    )

    print()
    print("AUDIT RECORD")
    print(audit)