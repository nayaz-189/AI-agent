import os
import subprocess
import webbrowser

from urllib.parse import quote_plus

from brain.application_resolver import find_application

from brain.website_cache import (
    get_cached_website,
    save_website,
)

from brain.website_resolver import (
    resolve_official_website,
)


def open_youtube():
    return open_website(
        "https://www.youtube.com"
    )


def open_google():
    return open_website(
        "https://www.google.com"
    )


def open_calculator():
    """Launch the fixed Calculator capability through both desktop gates."""
    from desktop.desktop_execution_gate import DesktopExecutionGate

    return DesktopExecutionGate().execute({
        "action": "open_calculator", "arguments": {},
    }).get("success") is True


def _open_calculator():
    """Private OS primitive; called only after desktop authorization."""
    import win32api

    subprocess.Popen(
        [os.path.join(win32api.GetSystemDirectory(), "calc.exe")],
        shell=False,
    )
    return True


def open_website(url):
    from tools.tool_registry import validate_tool_arguments

    if not validate_tool_arguments("open_website", {"url": url}):
        return False
    return webbrowser.open(url) is True


def resolve_website(target):
    target = target.lower().strip()

    print(
        f"Resolver received target: {target}"
    )

    # -------------------------
    # CACHE FIRST
    # -------------------------

    cached_url = get_cached_website(
        target
    )

    if cached_url:

        print(
            f"Cache hit: {cached_url}"
        )

        return open_website(
            cached_url
        )

    # -------------------------
    # SEARCH + IDENTITY
    # -------------------------

    print(
        "Cache miss. Searching for "
        "official website..."
    )

    resolved_url = (
        resolve_official_website(
            target
        )
    )

    # -------------------------
    # HIGH-CONFIDENCE RESULT
    # -------------------------

    if resolved_url:

        print(
            f"Resolved website: "
            f"{resolved_url}"
        )

        save_website(
            target,
            resolved_url,
        )

        print(
            f"Saved to cache: "
            f"{target} -> {resolved_url}"
        )

        return open_website(
            resolved_url
        )

    # -------------------------
    # UNCERTAIN RESULT
    # -------------------------

    print(
        "Could not safely identify "
        "official website."
    )

    query = quote_plus(
        f"{target} official website"
    )

    search_url = (
        "https://www.google.com/search?q="
        + query
    )

    print(
        "Opening search results instead."
    )

    return open_website(
        search_url
    )


def launch_application(
    launch_type,
    launch_target,
):
    """Public launch entry point; never bypass desktop authorization."""
    from desktop.desktop_execution_gate import DesktopExecutionGate

    return DesktopExecutionGate().execute({
        "action": "launch_application",
        "arguments": {
            "launch_type": launch_type,
            "launch_target": launch_target,
        },
    }).get("success") is True


def _launch_application(
    launch_type,
    launch_target,
):
    """
    Launch a previously resolved Windows application.

    Supported launch mechanisms:

    shortcut
        Traditional Start Menu .lnk file.

    app_id
        Windows application identity returned by
        Get-StartApps.
    """

    if not isinstance(
        launch_type,
        str,
    ):
        print(
            "Invalid application "
            "launch type."
        )
        return False

    if not isinstance(
        launch_target,
        str,
    ):
        print(
            "Invalid application "
            "launch target."
        )
        return False

    launch_type = (
        launch_type.strip()
    )

    launch_target = (
        launch_target.strip()
    )

    if not launch_target:

        print(
            "Application launch "
            "target is empty."
        )
        return False

    # -------------------------
    # START MENU SHORTCUT
    # -------------------------

    if launch_type == "shortcut":

        if not os.path.exists(
            launch_target
        ):

            print(
                "Application shortcut "
                "no longer exists."
            )

            return False

        print(
            "Launching shortcut:",
            launch_target,
        )

        try:

            os.startfile(
                launch_target
            )

            return True

        except OSError as error:

            print(
                "Failed to launch "
                f"shortcut: {error}"
            )

            return False

    # -------------------------
    # WINDOWS APP ID
    # -------------------------

    if launch_type == "app_id":
        import win32api

        print(
            "Launching Windows AppID:",
            launch_target,
        )

        try:

            subprocess.Popen(
                [
                    os.path.join(win32api.GetWindowsDirectory(), "explorer.exe"),
                    (
                        "shell:AppsFolder\\"
                        + launch_target
                    ),
                ],
                shell=False,
            )

            return True

        except OSError as error:

            print(
                "Failed to launch "
                f"Windows application: "
                f"{error}"
            )

            return False

    print(
        "Unsupported application "
        f"launch type: {launch_type}"
    )

    return False


def resolve_application(target):
    """
    Resolve and launch an installed application.

    This is retained as a registry-level capability,
    but application resolution is normally performed
    before execution so ambiguity can be handled by
    the runtime.
    """

    print(
        "Application resolver received:",
        target,
    )

    result = find_application(
        target
    )

    if not result:

        print(
            "Could not safely identify "
            "application."
        )

        return False

    status = result.get(
        "status"
    )

    if status == "ambiguous":

        print(
            "Application resolution "
            "requires clarification."
        )

        return False

    if status != "resolved":

        print(
            "Application resolver "
            "returned an invalid state."
        )

        return False

    application = result.get(
        "application"
    )

    if not isinstance(
        application,
        dict,
    ):

        print(
            "Resolved application "
            "data is invalid."
        )

        return False

    print(
        "Resolved application:",
        application.get("name"),
    )

    return launch_application(
        application.get(
            "launch_type"
        ),
        application.get(
            "launch_target"
        ),
    )
