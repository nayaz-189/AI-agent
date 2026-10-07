import time

import win32api
import win32con
import win32gui

from desktop.window_controller import (
    get_foreground_window,
)


class InputController:
    """
    Low-level Windows input primitives.

    IMPORTANT:
    This class is NOT an authorization layer.

    It must only be called after a higher-level
    action gate has verified that the requested
    window and action are permitted.

    It does not interpret natural language.
    It does not choose applications.
    It does not choose recipients.
    """

    def __init__(
        self,
        key_delay=0.02,
    ):
        self.key_delay = key_delay

    def _verify_foreground(
        self,
        expected_handle,
    ):
        """
        Require the expected HWND to be the
        foreground window.

        For input authority we deliberately use
        exact HWND matching rather than the more
        permissive same-process rule used by
        visual preparation.
        """

        if not isinstance(
            expected_handle,
            int,
        ):
            return {
                "verified": False,
                "error": (
                    "Expected window handle "
                    "must be an integer."
                ),
            }

        if not win32gui.IsWindow(
            expected_handle
        ):
            return {
                "verified": False,
                "error": (
                    "Expected window no longer "
                    "exists."
                ),
            }

        foreground = (
            get_foreground_window()
        )

        foreground_handle = (
            foreground.get("handle")
            if isinstance(
                foreground,
                dict,
            )
            else None
        )

        if (
            foreground_handle
            != expected_handle
        ):
            return {
                "verified": False,
                "foreground": foreground,
                "error": (
                    "Expected window is not the "
                    "exact foreground window."
                ),
            }

        return {
            "verified": True,
            "foreground": foreground,
            "error": None,
        }

    def type_text(
        self,
        expected_handle,
        text,
    ):
        """
        Type Unicode text into the currently
        focused control of an already verified
        foreground window.

        This method DOES NOT choose or click the
        target control.

        It also does not press Enter or submit
        anything.
        """

        result = {
            "success": False,
            "action": "type_text",
            "expected_handle": (
                expected_handle
            ),
            "characters": 0,
            "error": None,
        }

        verification = (
            self._verify_foreground(
                expected_handle
            )
        )

        if not verification[
            "verified"
        ]:
            result["error"] = (
                verification["error"]
            )
            return result

        if not isinstance(
            text,
            str,
        ):
            result["error"] = (
                "Text must be a string."
            )
            return result

        if not text:
            result["error"] = (
                "Text cannot be empty."
            )
            return result

        try:
            for character in text:

                win32api.SendMessage(
                    expected_handle,
                    win32con.WM_CHAR,
                    ord(character),
                    0,
                )

                time.sleep(
                    self.key_delay
                )

        except Exception as error:
            result["error"] = (
                f"Text input failed: {error}"
            )
            return result

        result["characters"] = len(
            text
        )

        result["success"] = True

        return result


if __name__ == "__main__":
    print(
        "InputController loaded."
    )
    print(
        "No input action executed."
    )