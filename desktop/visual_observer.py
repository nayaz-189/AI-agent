import os
import time

from desktop.visual_perception import (
    capture_prepared_window,
)


def observe_window(
    window,
    output_path,
):
    """
    Produce a verified visual observation of a
    discovered application window.

    Pipeline:
        discovered window
        -> foreground preparation
        -> foreground identity verification
        -> screenshot
        -> pixel validation
        -> structured observation

    This module does NOT interpret the screenshot,
    click, type, or interact with application content.
    """

    observation = {
        "success": False,
        "timestamp": time.time(),
        "window": None,
        "image": None,
        "capture_backend": None,
        "identity_verified": False,
        "pixel_validated": False,
        "ready_for_vision": False,
        "error": None,
    }

    if not isinstance(window, dict):
        observation["error"] = (
            "Invalid window data."
        )
        return observation

    # Keep only useful window identity information.
    observation["window"] = {
        "title": window.get("title"),
        "process_id": window.get(
            "process_id"
        ),
        "class_name": window.get(
            "class_name"
        ),
        "handle": window.get("handle"),
    }

    capture_result = (
        capture_prepared_window(
            window,
            output_path,
        )
    )

    if not capture_result.get(
        "success"
    ):
        observation["error"] = (
            capture_result.get("error")
            or "Window capture failed."
        )
        return observation

    observation[
        "identity_verified"
    ] = bool(
        capture_result.get(
            "identity_verified"
        )
    )

    capture = (
        capture_result.get(
            "capture"
        )
        or {}
    )

    validation = (
        capture.get(
            "validation"
        )
        or {}
    )

    observation[
        "pixel_validated"
    ] = bool(
        validation.get("valid")
    )

    observation[
        "capture_backend"
    ] = capture.get(
        "capture_backend"
    )

    image_path = capture.get(
        "output_path"
    )

    if (
        not image_path
        or not os.path.exists(
            image_path
        )
    ):
        observation["error"] = (
            "Capture succeeded but image "
            "file could not be verified."
        )
        return observation

    observation["image"] = {
        "path": image_path,
        "bounds": capture.get(
            "bounds"
        ),
        "validation": validation,
    }

    if not observation[
        "identity_verified"
    ]:
        observation["error"] = (
            "Target application identity "
            "was not verified."
        )
        return observation

    if not observation[
        "pixel_validated"
    ]:
        observation["error"] = (
            "Captured pixels were not valid."
        )
        return observation

    observation[
        "ready_for_vision"
    ] = True

    observation["success"] = True

    return observation


def summarize_observation(
    observation,
):
    """
    Print a compact diagnostic summary.
    """

    window = (
        observation.get("window")
        or {}
    )

    image = (
        observation.get("image")
        or {}
    )

    print(
        "Success:",
        observation.get("success"),
    )

    print(
        "Application:",
        window.get("title"),
    )

    print(
        "PID:",
        window.get("process_id"),
    )

    print(
        "HWND:",
        window.get("handle"),
    )

    print(
        "Identity verified:",
        observation.get(
            "identity_verified"
        ),
    )

    print(
        "Pixel validated:",
        observation.get(
            "pixel_validated"
        ),
    )

    print(
        "Capture backend:",
        observation.get(
            "capture_backend"
        ),
    )

    print(
        "Ready for vision:",
        observation.get(
            "ready_for_vision"
        ),
    )

    print(
        "Image:",
        image.get("path"),
    )

    print(
        "Error:",
        observation.get("error"),
    )


if __name__ == "__main__":
    print(
        "visual_observer.py is a "
        "library module."
    )