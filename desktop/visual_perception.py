import ctypes
import os

import win32gui
import win32ui
from PIL import Image, ImageGrab, ImageStat
from desktop.window_controller import (
    prepare_window_for_visual_capture,
)

# ---------------------------------------------------------
# Windows API
# ---------------------------------------------------------

_user32 = ctypes.windll.user32

PW_RENDERFULLCONTENT = 0x00000002


# ---------------------------------------------------------
# Window geometry
# ---------------------------------------------------------

def get_window_bounds(handle):
    """
    Return the outer screen coordinates of a HWND.
    """

    if not isinstance(handle, int) or handle <= 0:
        return None

    try:
        left, top, right, bottom = (
            win32gui.GetWindowRect(handle)
        )
    except Exception:
        return None

    width = right - left
    height = bottom - top

    if width <= 0 or height <= 0:
        return None

    return {
        "left": left,
        "top": top,
        "right": right,
        "bottom": bottom,
        "width": width,
        "height": height,
    }


# ---------------------------------------------------------
# Image validation
# ---------------------------------------------------------

def analyze_image(output_path):
    """
    Perform lightweight pixel validation.

    This does not attempt to understand the UI.
    It only determines whether the capture appears
    to contain meaningful pixel variation.
    """

    result = {
        "valid": False,
        "mean_brightness": None,
        "variation": None,
        "reason": None,
    }

    try:
        with Image.open(output_path) as image:

            image = image.convert("L")

            statistics = ImageStat.Stat(
                image
            )

            mean_brightness = (
                statistics.mean[0]
            )

            variation = (
                statistics.stddev[0]
            )

            result["mean_brightness"] = (
                round(mean_brightness, 2)
            )

            result["variation"] = (
                round(variation, 2)
            )

            # A nearly black image with essentially
            # no pixel variation is not useful visual
            # perception.

            if (
                mean_brightness < 3
                and variation < 3
            ):
                result["reason"] = (
                    "Capture appears black "
                    "or nearly blank."
                )
                return result

            result["valid"] = True
            result["reason"] = (
                "Capture contains visible "
                "pixel information."
            )

            return result

    except Exception as error:
        result["reason"] = str(error)
        return result


# ---------------------------------------------------------
# Backend 1: PrintWindow
# ---------------------------------------------------------

def capture_with_print_window(
    handle,
    output_path,
):
    """
    Ask Windows/application to render the target HWND.

    Some modern GPU-rendered applications may return
    success while producing a black image.
    """

    result = {
        "success": False,
        "backend": "print_window",
        "output_path": None,
        "error": None,
    }

    bounds = get_window_bounds(
        handle
    )

    if not bounds:
        result["error"] = (
            "Could not determine window bounds."
        )
        return result

    width = bounds["width"]
    height = bounds["height"]

    window_dc_handle = None
    source_dc = None
    memory_dc = None
    bitmap = None

    try:
        window_dc_handle = (
            win32gui.GetWindowDC(handle)
        )

        if not window_dc_handle:
            result["error"] = (
                "Could not obtain window DC."
            )
            return result

        source_dc = (
            win32ui.CreateDCFromHandle(
                window_dc_handle
            )
        )

        memory_dc = (
            source_dc.CreateCompatibleDC()
        )

        bitmap = win32ui.CreateBitmap()

        bitmap.CreateCompatibleBitmap(
            source_dc,
            width,
            height,
        )

        memory_dc.SelectObject(
            bitmap
        )

        api_result = (
            _user32.PrintWindow(
                handle,
                memory_dc.GetSafeHdc(),
                PW_RENDERFULLCONTENT,
            )
        )

        if api_result != 1:
            result["error"] = (
                "PrintWindow reported failure."
            )
            return result

        os.makedirs(
            os.path.dirname(output_path),
            exist_ok=True,
        )

        bitmap.SaveBitmapFile(
            memory_dc,
            output_path,
        )

        if not os.path.exists(output_path):
            result["error"] = (
                "Capture file was not created."
            )
            return result

        result["success"] = True
        result["output_path"] = output_path

        return result

    except Exception as error:
        result["error"] = str(error)
        return result

    finally:
        if bitmap is not None:
            try:
                win32gui.DeleteObject(
                    bitmap.GetHandle()
                )
            except Exception:
                pass

        if memory_dc is not None:
            try:
                memory_dc.DeleteDC()
            except Exception:
                pass

        if source_dc is not None:
            try:
                source_dc.DeleteDC()
            except Exception:
                pass

        if window_dc_handle is not None:
            try:
                win32gui.ReleaseDC(
                    handle,
                    window_dc_handle,
                )
            except Exception:
                pass


# ---------------------------------------------------------
# Backend 2: Actual screen pixels
# ---------------------------------------------------------

def capture_with_screen_region(
    handle,
    output_path,
):
    """
    Capture the screen rectangle occupied by a window.

    Unlike PrintWindow, this captures pixels actually
    displayed on the desktop.

    Important:
    another window covering the target will also appear
    in this capture.
    """

    result = {
        "success": False,
        "backend": "screen_region",
        "output_path": None,
        "error": None,
    }

    bounds = get_window_bounds(
        handle
    )

    if not bounds:
        result["error"] = (
            "Could not determine window bounds."
        )
        return result

    try:
        image = ImageGrab.grab(
            bbox=(
                bounds["left"],
                bounds["top"],
                bounds["right"],
                bounds["bottom"],
            ),
            all_screens=True,
        )

        parent = os.path.dirname(
            output_path
        )

        if parent:
            os.makedirs(
                parent,
                exist_ok=True,
            )

        image.save(output_path)

        if not os.path.exists(output_path):
            result["error"] = (
                "Screen-region capture "
                "was not created."
            )
            return result

        result["success"] = True
        result["output_path"] = output_path

        return result

    except Exception as error:
        result["error"] = str(error)
        return result


# ---------------------------------------------------------
# Automatic capture strategy
# ---------------------------------------------------------

def capture_window(
    handle,
    output_path,
):
    """
    Capture a window using an automatic fallback chain.

    Strategy:

        PrintWindow
            ↓
        pixel validation
            ↓
        valid → use it
        invalid → screen-region fallback
            ↓
        pixel validation

    This function remains perception-only.
    """

    result = {
        "success": False,
        "handle": handle,
        "output_path": None,
        "bounds": None,
        "capture_backend": None,
        "validation": None,
        "attempts": [],
        "error": None,
    }

    if not isinstance(handle, int) or handle <= 0:
        result["error"] = (
            "Invalid window handle."
        )
        return result

    if not isinstance(output_path, str):
        result["error"] = (
            "Invalid output path."
        )
        return result

    output_path = os.path.abspath(
        output_path
    )

    bounds = get_window_bounds(
        handle
    )

    if not bounds:
        result["error"] = (
            "Could not determine window bounds."
        )
        return result

    result["bounds"] = bounds

    # ------------------------------
    # Attempt 1: PrintWindow
    # ------------------------------

    print_result = (
        capture_with_print_window(
            handle,
            output_path,
        )
    )

    result["attempts"].append(
        print_result
    )

    if print_result["success"]:

        validation = analyze_image(
            output_path
        )

        if validation["valid"]:

            result["success"] = True
            result["output_path"] = (
                output_path
            )
            result["capture_backend"] = (
                "print_window"
            )
            result["validation"] = (
                validation
            )

            return result

    # ------------------------------
    # Attempt 2: Screen region
    # ------------------------------

    screen_result = (
        capture_with_screen_region(
            handle,
            output_path,
        )
    )

    result["attempts"].append(
        screen_result
    )

    if not screen_result["success"]:
        result["error"] = (
            screen_result["error"]
        )
        return result

    validation = analyze_image(
        output_path
    )

    result["validation"] = validation

    if not validation["valid"]:
        result["error"] = (
            validation["reason"]
        )
        return result

    result["success"] = True
    result["output_path"] = (
        output_path
    )
    result["capture_backend"] = (
        "screen_region"
    )

    return result
def capture_prepared_window(
    window,
    output_path,
):
    """
    Prepare a discovered window and capture it only
    after foreground ownership has been verified.

    This combines:
        window identity
        -> foreground preparation
        -> foreground verification
        -> visual capture
        -> pixel validation

    It does not click, type, or interact with
    application content.
    """

    result = {
        "success": False,
        "window": window,
        "preparation": None,
        "capture": None,
        "identity_verified": False,
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

    if (
        not isinstance(handle, int)
        or handle <= 0
    ):
        result["error"] = (
            "Window does not contain "
            "a valid handle."
        )
        return result

    preparation = (
        prepare_window_for_visual_capture(
            window
        )
    )

    result["preparation"] = preparation

    if not preparation.get(
        "success"
    ):
        result["error"] = (
            preparation.get("error")
            or "Window preparation failed."
        )
        return result

    foreground = (
        preparation
        .get("foreground", {})
    )

    if not foreground.get(
        "verified"
    ):
        result["error"] = (
            "Target foreground identity "
            "was not verified."
        )
        return result

    result[
        "identity_verified"
    ] = True

    capture = capture_window(
        handle,
        output_path,
    )

    result["capture"] = capture

    if not capture.get(
        "success"
    ):
        result["error"] = (
            capture.get("error")
            or "Visual capture failed."
        )
        return result

    result["success"] = True

    return result

if __name__ == "__main__":
    print(
        "visual_perception.py is a "
        "library module."
    )