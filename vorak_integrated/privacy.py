"""Conservative capture gate. Browser screenshots fail closed because tab URLs and
payment forms cannot be reliably identified from a window title alone.
"""
from __future__ import annotations
from vorak_integrated.screen_guard import classify as _hardened_classify
import re

SENSITIVE = re.compile(r'\b(pay(?:ment|ments)?|checkout|billing|invoice|card|credit|debit|bank(?:ing)?|upi|wallet|otp|password|sign[ -]?in|log[ -]?in|purchase|subscribe|subscription|stripe|razorpay|paypal|phonepe|paytm|google pay|gpay|netbanking)\b', re.I)
BROWSERS = re.compile(r'\b(chrome|edge|firefox|brave|opera|vivaldi|browser)\b', re.I)


def classify_window(title: str, executable: str = '') -> tuple[bool, str]:
    decision = _hardened_classify(title, executable)
    return decision.allowed, decision.reason


def foreground_window() -> tuple[str, str]:
    import ctypes
    from ctypes import wintypes
    user32=ctypes.windll.user32
    hwnd=user32.GetForegroundWindow()
    if not hwnd: return '', ''
    n=user32.GetWindowTextLengthW(hwnd)
    buf=ctypes.create_unicode_buffer(max(1,n+1))
    user32.GetWindowTextW(hwnd,buf,n+1)
    # If process name cannot be determined, fail closed for screenshot access.
    exe=''
    try:
        import psutil
        pid=wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        exe=psutil.Process(pid.value).name()
    except Exception:
        return buf.value, ''
    return buf.value, exe


def capture_safe_screen() -> tuple[bytes | None,str]:
    """Read-only. Captures foreground window only, never an entire desktop by default."""
    title,exe=foreground_window()
    if not exe: return None,'Foreground process could not be verified; capture blocked (install psutil).'
    allowed,why=classify_window(title,exe)
    if not allowed: return None,why
    try:
        import ctypes,io
        from PIL import ImageGrab
        hwnd=ctypes.windll.user32.GetForegroundWindow()
        rect=ctypes.wintypes.RECT()
        if not ctypes.windll.user32.GetWindowRect(hwnd,ctypes.byref(rect)):
            return None,'Window bounds unavailable.'
        bbox=(rect.left,rect.top,rect.right,rect.bottom)
        if bbox[2]<=bbox[0] or bbox[3]<=bbox[1]: return None,'Invalid window bounds.'
        shot=ImageGrab.grab(bbox=bbox,all_screens=True)
        # Recheck immediately after capture to avoid window-switch races.
        now_title,now_exe=foreground_window()
        if (now_title,now_exe)!=(title,exe): return None,'Window changed during capture; discarded.'
        shot.thumbnail((1280,720))
        out=io.BytesIO();shot.convert('RGB').save(out,format='JPEG',quality=72)
        return out.getvalue(), f'Captured allowed window: {title[:100]}'
    except Exception as exc:
        return None,'Screen capture unavailable: '+type(exc).__name__
