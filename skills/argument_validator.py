from urllib.parse import urlparse



# ============================================================
# AI AGENT ARGUMENT VALIDATOR
# ============================================================
#
# Validates argument VALUES before a capability can execute.
#
# Capability Broker:
#   "Is this skill allowed to request this capability?"
#
# Argument Validator:
#   "Are the supplied values safe and valid?"
#
# This module NEVER executes capabilities.
# ============================================================


MAX_URL_LENGTH = 2048

ALLOWED_WEB_SCHEMES = {
    "http",
    "https",
}


# ============================================================
# URL VALIDATION
# ============================================================

def validate_url(value):
    """
    Validate a URL intended for browser capabilities.
    """

    # Must be a string.
    if not isinstance(value, str):

        return {
            "valid": False,
            "reason": "URL must be a string.",
        }

    # Remove surrounding whitespace.
    value = value.strip()

    # Cannot be empty.
    if not value:

        return {
            "valid": False,
            "reason": "URL cannot be empty.",
        }

    # Prevent extremely large values.
    if len(value) > MAX_URL_LENGTH:

        return {
            "valid": False,
            "reason": "URL exceeds maximum length.",
        }

    # Parse URL.
    try:

        parsed = urlparse(value)

    except Exception:

        return {
            "valid": False,
            "reason": "URL could not be parsed.",
        }

    # Only normal web URLs are allowed.
    scheme = parsed.scheme.lower()

    if scheme not in ALLOWED_WEB_SCHEMES:

        return {
            "valid": False,
            "reason": (
                "URL scheme must be http or https."
            ),
        }

    # Hostname is mandatory.
    if not parsed.hostname:

        return {
            "valid": False,
            "reason": "URL must contain a hostname.",
        }

    # Reject URLs containing credentials.
    if (
        parsed.username is not None
        or parsed.password is not None
    ):

        return {
            "valid": False,
            "reason": (
                "URLs containing embedded credentials "
                "are not allowed."
            ),
        }

    return {
        "valid": True,
        "reason": "URL passed validation.",
        "value": value,
    }


# ============================================================
# OPEN WEBSITE VALIDATION
# ============================================================

def validate_open_website(arguments):
    """
    Validate arguments for the open_website capability.
    """

    if "url" not in arguments:

        return {
            "valid": False,
            "reason": (
                "open_website requires a URL."
            ),
        }

    url_result = validate_url(
        arguments["url"]
    )

    if not url_result["valid"]:

        return {
            "valid": False,
            "reason": url_result["reason"],
            "argument": "url",
        }

    return {
        "valid": True,
        "reason": (
            "open_website arguments passed validation."
        ),
        "arguments": {
            "url": url_result["value"],
        },
    }


# ============================================================
# CAPABILITY VALIDATOR REGISTRY
# ============================================================

CAPABILITY_VALIDATORS = {

    "open_website": validate_open_website,

}


# ============================================================
# MAIN VALIDATION ENTRYPOINT
# ============================================================

def validate_capability_arguments(
    capability,
    arguments,
):
    """
    Validate arguments for a registered capability.

    Fail closed:
    if no validator exists, reject the request.
    """

    if not isinstance(arguments, dict):

        return {
            "valid": False,
            "reason": (
                "Capability arguments must be a dictionary."
            ),
        }

    validator = CAPABILITY_VALIDATORS.get(
        capability
    )

    if validator is None:

        return {
            "valid": False,
            "reason": (
                "No argument validator is registered "
                "for this capability."
            ),
        }

    return validator(arguments)


# ============================================================
# DEVELOPMENT TESTS
# ============================================================

if __name__ == "__main__":

    tests = [

        (
            "VALID HTTPS",
            "https://example.com",
        ),

        (
            "VALID HTTP",
            "http://example.com/test",
        ),

        (
            "NOT STRING",
            12345,
        ),

        (
            "EMPTY",
            "",
        ),

        (
            "FILE SCHEME",
            "file:///C:/Windows/System32",
        ),

        (
            "JAVASCRIPT SCHEME",
            "javascript:alert(1)",
        ),

        (
            "DATA SCHEME",
            "data:text/html,test",
        ),

        (
            "NO HOSTNAME",
            "https://",
        ),

        (
            "EMBEDDED CREDENTIALS",
            "https://user:password@example.com",
        ),
    ]

    print()
    print("ARGUMENT VALIDATOR TEST")
    print("==============================")

    for name, url in tests:

        result = validate_capability_arguments(
            "open_website",
            {
                "url": url,
            },
        )

        print()
        print(name)
        print("Valid:", result["valid"])
        print("Reason:", result["reason"])