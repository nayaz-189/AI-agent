from pywinauto import Desktop


def inspect_window_controls(
    handle,
    max_controls=200,
):
    """
    Inspect UI Automation controls exposed by a
    specific Windows HWND.

    This operation is read-only.

    Returns a structured result describing whether
    the window can be inspected and which semantic
    controls are available.
    """

    result = {
        "success": False,
        "handle": handle,
        "control_count": 0,
        "controls": [],
        "error": None,
    }

    if (
        not isinstance(handle, int)
        or handle <= 0
    ):
        result["error"] = (
            "Invalid window handle."
        )
        return result

    try:
        window = (
            Desktop(
                backend="uia"
            )
            .window(
                handle=handle
            )
        )

        if not window.exists():
            result["error"] = (
                "Window does not exist."
            )
            return result

        wrapper = (
            window.wrapper_object()
        )

        descendants = (
            wrapper.descendants()
        )

    except Exception as error:
        result["error"] = str(error)
        return result

    controls = []

    for control in descendants[
        :max_controls
    ]:

        try:
            element = (
                control.element_info
            )

            controls.append(
                {
                    "name": (
                        control.window_text()
                        or ""
                    ),
                    "control_type": getattr(
                        element,
                        "control_type",
                        None,
                    ),
                    "class_name": getattr(
                        element,
                        "class_name",
                        None,
                    ),
                    "automation_id": getattr(
                        element,
                        "automation_id",
                        None,
                    ),
                    "handle": getattr(
                        element,
                        "handle",
                        None,
                    ),
                }
            )

        except Exception:
            continue

    result["success"] = True
    result["control_count"] = len(
        controls
    )
    result["controls"] = controls

    return result


def summarize_control_types(
    inspection,
):
    """
    Count the semantic UI control types found in an
    inspection result.
    """

    summary = {}

    controls = inspection.get(
        "controls",
        [],
    )

    for control in controls:

        control_type = (
            control.get(
                "control_type"
            )
            or "Unknown"
        )

        summary[control_type] = (
            summary.get(
                control_type,
                0,
            )
            + 1
        )

    return summary


def has_interactive_controls(
    inspection,
):
    """
    Determine whether UI Automation exposes useful
    application-content controls.

    Window-management chrome such as Minimize,
    Maximize, and Close does not count as usable
    application content.

    This function performs capability detection only.
    It does not interact with the application.
    """

    interactive_types = {
        "Button",
        "Edit",
        "ComboBox",
        "List",
        "ListItem",
        "MenuItem",
        "TabItem",
        "TreeItem",
        "CheckBox",
        "RadioButton",
        "Hyperlink",
    }

    window_chrome_names = {
        "system",
        "minimize",
        "maximize",
        "restore",
        "close",
    }

    window_chrome_types = {
        "TitleBar",
        "MenuBar",
    }

    for control in inspection.get(
        "controls",
        [],
    ):

        control_type = control.get(
            "control_type"
        )

        control_name = str(
            control.get(
                "name",
                "",
            )
            or ""
        ).strip().lower()

        if control_type in window_chrome_types:
            continue

        if control_name in window_chrome_names:
            continue

        if control_type in interactive_types:
            return True

    return False
def print_inspection(
    inspection,
):
    """
    Human-readable diagnostic output.
    """

    print(
        "Inspection success:",
        inspection.get(
            "success"
        ),
    )

    print(
        "Handle:",
        inspection.get(
            "handle"
        ),
    )

    print(
        "Controls:",
        inspection.get(
            "control_count"
        ),
    )

    error = inspection.get(
        "error"
    )

    if error:
        print(
            "Error:",
            error,
        )
        return

    print(
        "Control types:",
        summarize_control_types(
            inspection
        ),
    )

    print(
        "Interactive controls:",
        has_interactive_controls(
            inspection
        ),
    )

    print()

    for index, control in enumerate(
        inspection.get(
            "controls",
            []
        ),
        start=1,
    ):

        print(
            f"{index}. "
            f"{control['control_type']} | "
            f"{control['name']!r} | "
            f"class={control['class_name']!r} | "
            f"automation_id="
            f"{control['automation_id']!r}"
        )


if __name__ == "__main__":
    print(
        "ui_inspector.py is a library module."
    )
    print(
        "Pass a discovered HWND to "
        "inspect_window_controls()."
    )