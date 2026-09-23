from brain.application_resolver import find_application


def clean_command(command):
    command = command.lower().strip()

    if command.startswith("you:"):
        command = command[4:].strip()

    return command


def fast_route(command):
    command = clean_command(command)

    prefixes = [
        "open ",
        "go to ",
        "take me to ",
    ]

    for prefix in prefixes:

        if not command.startswith(prefix):
            continue

        target = command[len(prefix):].strip()

        if not target:
            return None

        app_result = find_application(target)

        # Confident application match
        if (
            app_result
            and app_result["status"] == "resolved"
        ):
            app = app_result["application"]

            return {
                "tool": "launch_application",
                "arguments": {
                    "path": app["path"]
                }
            }

        # Multiple possible applications
        if (
            app_result
            and app_result["status"] == "ambiguous"
        ):
            return {
                "type": "clarification",
                "target": target,
                "candidates": app_result["candidates"],
            }

        # No installed application matched.
        # Treat it as a website/service.
        return {
            "tool": "resolve_website",
            "arguments": {
                "target": target
            }
        }

    return None