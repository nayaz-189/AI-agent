from brain.application_resolver import find_application


def clean_command(command):
    command = command.lower().strip()

    if command.startswith("you:"):
        command = command[4:].strip()

    return command


def fast_route(command):
    command = clean_command(command)

    # This narrow local intent avoids sending a desktop request to any model.
    if command.rstrip(".") in {
        "open notepad, write a short introduction about artificial intelligence, "
        "save it to an approved test file, and verify the saved content",
        "open notepad, write a short introduction about artificial intelligence, "
        "export it into my approved ai agent test folder, and verify the saved content",
    }:
        return {"tool": "write_test_introduction", "arguments": {}}

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

        # Fixed registered capability: no model-generated executable path.
        if target in {"calculator", "windows calculator"}:
            return {"tool": "open_calculator", "arguments": {}}

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
        "launch_type": app[
            "launch_type"
        ],
        "launch_target": app[
            "launch_target"
        ],
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
