"""Local user interaction only; never registered as an agent capability."""

import ctypes
from ctypes import wintypes
import json
import os


def confirm_desktop_request(request):
    """Real Windows Yes/No dialog, default No, 60-second timeout.

    No stdin, planner field, environment flag or step ID can supply consent.
    This is an application permission prompt, not a Windows security prompt.
    """
    if os.name != "nt" or not isinstance(request, dict):
        return False
    proposal = json.dumps(request, ensure_ascii=True, sort_keys=True, indent=2)
    if len(proposal) > 8000:
        return False
    message = (
        "AI Agent requests your permission for this exact test-document action.\n"
        "Choose Yes only if you approve. No response cancels after 60 seconds.\n"
        "Export creates a new UTF-8 file; the Notepad tab remains unsaved.\n\n"
        + proposal
    )
    try:
        dialog = ctypes.windll.user32.MessageBoxTimeoutW
        dialog.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR,
                           wintypes.UINT, wintypes.WORD, wintypes.DWORD]
        dialog.restype = ctypes.c_int
        # YESNO | ICONQUESTION | DEFBUTTON2 | SETFOREGROUND
        return dialog(None, message, "AI Agent — Test document permission",
                      0x4 | 0x20 | 0x100 | 0x10000, 0, 60000) == 6
    except Exception:
        return False
