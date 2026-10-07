from desktop.ui_inspector import (
    inspect_window_controls,
    has_interactive_controls,
)


def analyze_window_capabilities(window):
    """
    Analyze which perception/control mechanisms are
    available for a discovered window.

    This function does not click, type, focus, or modify
    the target application.
    """

    result = {
        "window": window,
        "win32_available": False,
        "uia_available": False,
        "uia_content_available": False,
        "recommended_backend": None,
        "inspection": None,
        "reason": None,
    }

    if not isinstance(window, dict):
        result["reason"] = (
            "Window data is invalid."
        )
        return result

    handle = window.get("handle")

    if (
        not isinstance(handle, int)
        or handle <= 0
    ):
        result["reason"] = (
            "Window does not contain a valid handle."
        )
        return result

    # If we have a valid HWND, raw Win32-level
    # window management is available.

    result["win32_available"] = True

    # Attempt semantic UI Automation inspection.

    inspection = inspect_window_controls(
        handle
    )

    result["inspection"] = inspection

    if not inspection.get("success"):
        result["recommended_backend"] = "visual"
        result["reason"] = (
            "UI Automation could not inspect "
            "the window."
        )
        return result

    result["uia_available"] = True

    # Determine whether UIA exposes useful
    # application-content controls rather than
    # only title-bar/window-management controls.

    if has_interactive_controls(
        inspection
    ):
        result[
            "uia_content_available"
        ] = True

        result[
            "recommended_backend"
        ] = "uia"

        result["reason"] = (
            "Useful semantic application "
            "controls are available."
        )

        return result

    # The window exists and UIA can attach,
    # but the application content itself is
    # not semantically accessible.

    result[
        "recommended_backend"
    ] = "visual"

    result["reason"] = (
        "The window is accessible, but UI "
        "Automation exposes no useful "
        "application-content controls."
    )

    return result


def print_capability_analysis(
    analysis,
):
    """
    Human-readable diagnostic output.
    """

    window = analysis.get(
        "window",
        {},
    )

    print(
        "Window:",
        window.get(
            "title",
            "<unknown>",
        ),
    )

    print(
        "Handle:",
        window.get(
            "handle",
        ),
    )

    print(
        "Win32 available:",
        analysis.get(
            "win32_available"
        ),
    )

    print(
        "UIA available:",
        analysis.get(
            "uia_available"
        ),
    )

    print(
        "UIA application content:",
        analysis.get(
            "uia_content_available"
        ),
    )

    print(
        "Recommended backend:",
        analysis.get(
            "recommended_backend"
        ),
    )

    print(
        "Reason:",
        analysis.get(
            "reason"
        ),
    )


if __name__ == "__main__":
    print(
        "perception.py is a library module."
    )