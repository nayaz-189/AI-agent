"""Read-only Calculator observation, independent of tool return values."""

import ctypes
from ctypes import wintypes
import ntpath
import re
import time

from desktop.window_manager import get_win32_windows


def _process_image(process_id):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x1000, False, process_id)
    if not handle:
        return None
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return buffer.value
        return None
    finally:
        kernel.CloseHandle(handle)


def _program_files_directory():
    from win32com.shell import shell, shellcon

    return shell.SHGetFolderPath(0, shellcon.CSIDL_PROGRAM_FILES, None, 0)


def _is_calculator_image(path):
    import win32api

    if not isinstance(path, str):
        return False
    path = ntpath.normcase(ntpath.normpath(path))
    legacy = ntpath.join(win32api.GetSystemDirectory(), "calc.exe")
    if path == ntpath.normcase(legacy):
        return True
    # A title alone is not evidence: require the Calculator package process.
    package_root = ntpath.normcase(ntpath.join(_program_files_directory(), "WindowsApps"))
    if not path.startswith(package_root + "\\"):
        return False
    parts = path[len(package_root) + 1:].split("\\")
    return (
        ntpath.basename(path) in {"calculatorapp.exe", "calculator.exe"}
        and re.fullmatch(
            r"microsoft\.windowscalculator_\d+\.\d+\.\d+\.\d+_(?:x64|x86|arm64)_.*_8wekyb3d8bbwe",
            parts[0],
        ) is not None
    )


def observe_calculator(timeout=5.0, poll_interval=0.1):
    """Wait briefly for a visible, non-minimized Calculator-owned window.

    UWP versions may use ApplicationFrameHost for the top-level window, so
    inspect child process identities too. Access failures fail verification.
    """
    import win32gui
    import win32process

    if timeout < 0 or poll_interval <= 0:
        raise ValueError("Observation needs a non-negative timeout and positive poll interval.")
    deadline = time.monotonic() + timeout
    while True:
        for window in get_win32_windows(include_titles=False):
            handle = window.get("handle")
            if not handle or window.get("visible") is not True:
                continue
            try:
                if win32gui.IsIconic(handle):
                    continue
                process_ids = {window["process_id"]}

                def collect(child, _):
                    if win32gui.IsWindowVisible(child):
                        process_ids.add(win32process.GetWindowThreadProcessId(child)[1])
                    return True

                win32gui.EnumChildWindows(handle, collect, None)
                for process_id in process_ids:
                    if _is_calculator_image(_process_image(process_id)):
                        return {
                            "calculator_open": True,
                            "window_handle": handle,
                            "process_id": process_id,
                            "observation": "visible Calculator process window",
                        }
            except Exception:
                # Windows can disappear between enumeration and inspection.
                continue
        if time.monotonic() >= deadline:
            return {"calculator_open": False}
        time.sleep(min(poll_interval, max(0, deadline - time.monotonic())))
