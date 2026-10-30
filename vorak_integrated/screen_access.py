"""VORAK's one-shot, approval-gated Windows screenshot boundary.

No microphone, screen, OS or network access at import time. This is not a
payment-detection guarantee: browser content is always denied, and unknown
foreground/window identities fail closed. Screenshots are never stored here.
"""
from __future__ import annotations

from dataclasses import dataclass
import io
import os
import re

SENSITIVE = re.compile(
    r"(?i)\b(?:pay(?:ment|ments)?|checkout|billing|invoice|card(?:holder)?|credit|debit|"
    r"bank(?:ing)?|upi|wallet|otp|password|passcode|credential|two[ -]?factor|2fa|"
    r"purchase|subscribe|subscription|stripe|razorpay|paypal|phonepe|paytm|"
    r"google pay|gpay|netbanking|authenticat(?:ion|or)|sign[ -]?in|log[ -]?in|"
    r"incognito|private browsing|security settings|account settings)\b"
)
BROWSERS = frozenset({"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "vivaldi.exe", "arc.exe"})
BLOCKED_EXES = frozenset({"1password.exe", "bitwarden.exe", "keepass.exe", "keepassxc.exe", "authy.exe", "credentialui.exe", "consent.exe"})


@dataclass(frozen=True)
class VisibleWindow:
    hwnd: int
    title: str
    executable: str
    rect: tuple[int, int, int, int]
    minimized: bool = False


def policy(title: str, executable: str) -> tuple[bool, str]:
    """Unknown identities, browser tabs and credential/payment contexts are denied."""
    if not title or not title.strip() or not executable or not executable.strip():
        return False, "Window identity is unknown."
    exe = executable.casefold()
    if exe in BROWSERS or "browser" in exe:
        return False, "Browser windows are blocked: payment pages cannot be verified securely."
    if exe in BLOCKED_EXES or SENSITIVE.search(title + " " + executable):
        return False, "Sensitive, payment or credential-related window blocked."
    return True, "Verified non-browser app."


def intersects(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def _windows_snapshot() -> tuple[VisibleWindow, list[VisibleWindow]]:
    if os.name != "nt":
        raise RuntimeError("Windows only")
    import ctypes
    from ctypes import wintypes
    import psutil

    user32 = ctypes.windll.user32
    # Windows handles are pointer-sized; default ctypes return types can truncate HWNDs.
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    fg = user32.GetForegroundWindow()
    if not fg:
        raise RuntimeError("No foreground window")
    items: list[VisibleWindow] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def record(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        bounds = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(bounds)):
            return True
        rect = (bounds.left, bounds.top, bounds.right, bounds.bottom)
        if rect[2]-rect[0] < 90 or rect[3]-rect[1] < 60:
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(max(1, n + 1))
        user32.GetWindowTextW(hwnd, buf, n + 1)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        try:
            executable = psutil.Process(pid.value).name()
        except Exception:
            executable = ""
        items.append(VisibleWindow(int(hwnd), buf.value, executable, rect))
        return True

    cb = callback_type(record)
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    if not user32.EnumWindows(cb, 0):
        raise RuntimeError("Window enumeration failed")
    foreground = next((w for w in items if w.hwnd == int(fg)), None)
    if foreground is None:
        raise RuntimeError("Foreground identity not verified")
    return foreground, items


def validate_capture(scope: str, fg: VisibleWindow, visible: list[VisibleWindow]) -> tuple[bool, str, tuple[int,int,int,int]|None]:
    """Return permission plus crop bounds. No pixel data reaches this function."""
    if scope not in {"window", "desktop"}:
        return False, "Invalid screen scope.", None
    allowed, why = policy(fg.title, fg.executable)
    if scope == "desktop":
        # Avoid photographing browsers/credential screens hidden behind other apps.
        # Windows' Explorer shell has various window titles; process name matters.
        if fg.executable.casefold() != "explorer.exe":
            return False, "Desktop capture requires Windows Explorer desktop in the foreground.", None
        if SENSITIVE.search(fg.title):
            return False, "Sensitive desktop context detected.", None
    elif not allowed:
        return False, why, None
    rect = fg.rect if scope == "window" else None
    for w in visible:
        if w.hwnd == fg.hwnd or w.minimized:
            continue
        # Some shell windows have no title; never approve one hiding protected content.
        if not w.title:
            # A title-less browser/secret window is still protected.
            if not w.executable or w.executable.casefold() in BROWSERS | BLOCKED_EXES:
                return False, "Unknown or protected visible window; capture denied.", None
            continue
        if rect is not None and not intersects(w.rect, rect):
            continue
        valid, reason = policy(w.title, w.executable)
        if not valid:
            return False, "Potentially sensitive or browser window could be included in capture.", None
    return True, "One-shot " + scope + " capture approved by policy.", rect


def capture(scope: str = "window", *, snapshot=None, grabber=None):
    """Return (JPEG bytes, safe result note) or (None, denial).

    The caller MUST obtain physical owner confirmation before invoking capture.
    Foreground and visible-window identities are checked before AND after capture.
    """
    snapshot = snapshot or _windows_snapshot
    try:
        before, all_before = snapshot()
        allowed, reason, rect = validate_capture(scope, before, all_before)
        if not allowed:
            return None, reason
        if grabber is None:
            from PIL import ImageGrab
            grabber = ImageGrab.grab
        image = grabber(bbox=rect, all_screens=True)
        after, all_after = snapshot()
        allowed_after, reason_after, rect_after = validate_capture(scope, after, all_after)
        if not allowed_after or rect != rect_after or before.hwnd != after.hwnd or before.executable != after.executable:
            return None, "Window changed or privacy policy changed during capture; image discarded."
        # Verify the visible-window identities are stable against races.
        earlier = {(w.hwnd,w.title,w.executable) for w in all_before if w.title}
        later = {(w.hwnd,w.title,w.executable) for w in all_after if w.title}
        if earlier != later:
            return None, "Visible windows changed during capture; image discarded."
        image.thumbnail((1440, 900))
        out = io.BytesIO()
        image.convert("RGB").save(out, format="JPEG", quality=72, optimize=True)
        if out.tell() > 3_000_000:
            return None, "Screenshot is too large for safe inspection."
        return out.getvalue(), "Captured an approved " + scope + "."
    except Exception as exc:
        return None, "Windows screenshot unavailable: " + type(exc).__name__
