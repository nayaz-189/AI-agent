from pywinauto import Desktop

import win32gui
import win32process


def get_uia_windows():
    """
    Discover top-level windows exposed through
    Microsoft UI Automation.

    Read-only.
    """

    windows = []

    try:
        desktop = Desktop(
            backend="uia"
        )

        top_windows = desktop.windows()

    except Exception as error:

        print(
            "UI Automation inspection failed:",
            error,
        )

        return []

    for window in top_windows:

        try:
            title = (
                window.window_text()
                .strip()
            )

            element = (
                window.element_info
            )

            windows.append(
                {
                    "source": "uia",
                    "title": title,
                    "process_id": getattr(
                        element,
                        "process_id",
                        None,
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
                    "handle": getattr(
                        element,
                        "handle",
                        None,
                    ),
                    "visible": True,
                }
            )

        except Exception:
            # Windows can disappear while
            # enumeration is taking place.
            continue

    return windows


def get_win32_windows(*, include_titles=True):
    """
    Discover raw top-level Win32 windows.

    Unlike UI Automation, this can reveal windows
    that are hidden or represented unusually by
    modern Windows applications.

    Read-only.
    """

    windows = []

    def enum_callback(
        handle,
        results,
    ):
        try:
            _, process_id = (
                win32process
                .GetWindowThreadProcessId(
                    handle
                )
            )

            title = (
                win32gui
                .GetWindowText(
                    handle
                )
            ) if include_titles else ""

            class_name = (
                win32gui
                .GetClassName(
                    handle
                )
            )

            visible = bool(
                win32gui
                .IsWindowVisible(
                    handle
                )
            )

            results.append(
                {
                    "source": "win32",
                    "title": title,
                    "process_id":
                        process_id,
                    "control_type":
                        None,
                    "class_name":
                        class_name,
                    "handle": handle,
                    "visible": visible,
                }
            )

        except Exception:
            # Ignore windows that disappear or
            # become inaccessible during enumeration.
            pass

        return True

    try:

        win32gui.EnumWindows(
            enum_callback,
            windows,
        )

    except Exception as error:

        print(
            "Win32 inspection failed:",
            type(error).__name__,
        )

    return windows


def get_all_windows():
    """
    Build a unified view using both UI Automation
    and raw Win32 discovery.

    Duplicate HWNDs are merged when possible.
    """

    combined = {}

    # -------------------------
    # WIN32 FOUNDATION
    # -------------------------

    for window in get_win32_windows():

        handle = window.get(
            "handle"
        )

        if handle:
            combined[handle] = window

    # -------------------------
    # UIA ENRICHMENT
    # -------------------------

    for window in get_uia_windows():

        handle = window.get(
            "handle"
        )

        if (
            handle
            and handle in combined
        ):
            existing = combined[
                handle
            ]

            existing[
                "source"
            ] = "win32+uia"

            if window.get(
                "title"
            ):
                existing[
                    "title"
                ] = window[
                    "title"
                ]

            if window.get(
                "control_type"
            ):
                existing[
                    "control_type"
                ] = window[
                    "control_type"
                ]

            if window.get(
                "class_name"
            ):
                existing[
                    "class_name"
                ] = window[
                    "class_name"
                ]

        elif handle:

            combined[
                handle
            ] = window

    return list(
        combined.values()
    )


def find_windows(
    query,
    include_hidden=True,
):
    """
    Search the unified window model.

    Matches against:
    - title
    - class name

    Matching is case-insensitive.
    """

    if not isinstance(
        query,
        str,
    ):
        return []

    query = (
        query.strip().lower()
    )

    if not query:
        return []

    matches = []

    for window in get_all_windows():

        if (
            not include_hidden
            and not window.get(
                "visible",
                False,
            )
        ):
            continue

        title = str(
            window.get(
                "title",
                "",
            )
            or ""
        )

        class_name = str(
            window.get(
                "class_name",
                "",
            )
            or ""
        )

        searchable = (
            title
            + " "
            + class_name
        ).lower()

        if query in searchable:

            matches.append(
                window
            )

    return matches


def find_windows_by_process(
    process_id,
):
    """
    Return every discovered window belonging
    to a specific process ID.

    Read-only.
    """

    if not isinstance(
        process_id,
        int,
    ):
        return []

    return [
        window
        for window in get_all_windows()
        if window.get(
            "process_id"
        ) == process_id
    ]


def print_window(
    window,
    index=None,
):
    """
    Human-readable diagnostic representation.
    """

    prefix = ""

    if index is not None:
        prefix = f"{index}. "

    title = (
        window.get("title")
        or "<no title>"
    )

    print(
        f"{prefix}{title}"
    )

    print(
        "   Source:",
        window.get("source"),
    )

    print(
        "   PID:",
        window.get("process_id"),
    )

    print(
        "   Visible:",
        window.get("visible"),
    )

    print(
        "   Type:",
        window.get("control_type"),
    )

    print(
        "   Class:",
        window.get("class_name"),
    )

    print(
        "   Handle:",
        window.get("handle"),
    )


def print_visible_windows():
    """
    Print windows currently marked as visible
    by the unified desktop model.
    """

    windows = [
        window
        for window in get_all_windows()
        if window.get(
            "visible",
            False,
        )
    ]

    print(
        f"Visible windows: "
        f"{len(windows)}"
    )

    for index, window in enumerate(
        windows,
        start=1,
    ):

        print()

        print_window(
            window,
            index=index,
        )


if __name__ == "__main__":

    print_visible_windows()
