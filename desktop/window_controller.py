import ctypes
import time

import win32con
import win32gui
import win32process


_user32 = ctypes.windll.user32


def window_exists(handle):
    """
    Check whether an HWND still represents
    a valid Windows window.
    """

    if not isinstance(handle, int) or handle <= 0:
        return False

    try:
        return bool(
            win32gui.IsWindow(handle)
        )
    except Exception:
        return False


def get_window_process_id(handle):
    """
    Return the process ID that owns a window.
    """

    if not window_exists(handle):
        return None

    try:
        _, process_id = (
            win32process.GetWindowThreadProcessId(
                handle
            )
        )

        return process_id

    except Exception:
        return None


def get_foreground_window():
    """
    Return structured information about the
    current foreground window.
    """

    try:
        handle = (
            win32gui.GetForegroundWindow()
        )

        if not handle:
            return None

        process_id = (
            get_window_process_id(
                handle
            )
        )

        try:
            title = (
                win32gui.GetWindowText(
                    handle
                )
            )
        except Exception:
            title = ""

        return {
            "handle": handle,
            "process_id": process_id,
            "title": title,
        }

    except Exception:
        return None


def is_minimized(handle):
    """
    Determine whether a window is minimized.
    """

    if not window_exists(handle):
        return False

    try:
        return bool(
            win32gui.IsIconic(handle)
        )
    except Exception:
        return False


def restore_window(handle):
    """
    Restore a minimized window.

    This changes only window state.
    It does not interact with application content.
    """

    result = {
        "success": False,
        "handle": handle,
        "action": "restore",
        "error": None,
    }

    if not window_exists(handle):
        result["error"] = (
            "Target window does not exist."
        )
        return result

    try:
        if is_minimized(handle):
            win32gui.ShowWindow(
                handle,
                win32con.SW_RESTORE,
            )

            time.sleep(0.25)

        result["success"] = True
        return result

    except Exception as error:
        result["error"] = str(error)
        return result


def bring_to_foreground(
    handle,
    wait_seconds=0.5,
):
    """
    Attempt to make the target HWND the foreground
    window and verify the result.

    Windows intentionally restricts applications
    from stealing foreground focus, so this function
    may fail safely instead of assuming success.
    """

    result = {
        "success": False,
        "handle": handle,
        "expected_process_id": None,
        "foreground": None,
        "verified": False,
        "error": None,
    }

    if not window_exists(handle):
        result["error"] = (
            "Target window does not exist."
        )
        return result

    expected_process_id = (
        get_window_process_id(
            handle
        )
    )

    result[
        "expected_process_id"
    ] = expected_process_id

    try:
        if is_minimized(handle):
            win32gui.ShowWindow(
                handle,
                win32con.SW_RESTORE,
            )

            time.sleep(0.25)

        # Show without assuming that ShowWindow
        # successfully grants keyboard focus.

        win32gui.ShowWindow(
            handle,
            win32con.SW_SHOW,
        )

        try:
            win32gui.SetForegroundWindow(
                handle
            )
        except Exception:
            # Verification below is authoritative.
            # We do not claim success just because
            # the API call was attempted.
            pass

        time.sleep(wait_seconds)

        foreground = (
            get_foreground_window()
        )

        result["foreground"] = (
            foreground
        )

        if not foreground:
            result["error"] = (
                "Could not determine "
                "foreground window."
            )
            return result

        # Exact HWND match is the strongest result.

        if foreground["handle"] == handle:
            result["success"] = True
            result["verified"] = True
            return result

        # A single application can own multiple HWNDs.
        # Process identity is therefore also useful.

        if (
            expected_process_id is not None
            and foreground["process_id"]
            == expected_process_id
        ):
            result["success"] = True
            result["verified"] = True
            return result

        result["error"] = (
            "Foreground verification failed. "
            "Another window still owns focus."
        )

        return result

    except Exception as error:
        result["error"] = str(error)
        return result


def prepare_window_for_visual_capture(
    window,
):
    """
    Prepare a discovered window for visual perception.

    This function:
      1. validates the HWND,
      2. restores it if minimized,
      3. attempts foreground activation,
      4. verifies foreground ownership.

    It performs no clicks, typing, or application-
    content interaction.
    """

    result = {
        "success": False,
        "window": window,
        "restore": None,
        "foreground": None,
        "error": None,
    }

    if not isinstance(window, dict):
        result["error"] = (
            "Invalid window data."
        )
        return result

    handle = window.get(
        "handle"
    )

    if not window_exists(handle):
        result["error"] = (
            "Window handle is no longer valid."
        )
        return result

    restore_result = (
        restore_window(
            handle
        )
    )

    result["restore"] = (
        restore_result
    )

    if not restore_result["success"]:
        result["error"] = (
            restore_result["error"]
        )
        return result

    foreground_result = (
        bring_to_foreground(
            handle
        )
    )

    result["foreground"] = (
        foreground_result
    )

    if not foreground_result["success"]:
        result["error"] = (
            foreground_result["error"]
        )
        return result

    if not foreground_result["verified"]:
        result["error"] = (
            "Foreground ownership was "
            "not verified."
        )
        return result

    result["success"] = True
    return result


if __name__ == "__main__":
    print(
        "window_controller.py is "
        "a library module."
    )