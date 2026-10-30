"""Fail-closed, one-shot, foreground-screen protection for VORAK.

Only explicitly approved *non-browser* windows can be captured. This is not
payment-page detection, nor a guarantee that sensitive data is absent from
otherwise ordinary apps. No recording or periodic background capture.
"""
from __future__ import annotations
import re
from dataclasses import dataclass

DENY = re.compile(r"(?i)(pay(?:ment)?|bank|checkout|billing|invoice|card|upi|wallet|otp|password|passcode|credential|log.?in|sign.?in|subscribe|purchase|crypto|stripe|razorpay|paypal|phonepe|paytm|gpay|google pay|authenticat|account|security|private|incognito|secret|settings)")
BROWSER_EXES = frozenset({'chrome.exe','msedge.exe','firefox.exe','brave.exe','opera.exe','vivaldi.exe','arc.exe'})
BROWSER_TITLE = re.compile(r'(?i)chrome|edge|firefox|brave|opera|vivaldi|browser')
DENY_EXES = frozenset({'1password.exe','bitwarden.exe','keepass.exe','keepassxc.exe','authy.exe','credentialui.exe','consent.exe','powershell.exe','pwsh.exe','cmd.exe','windowsterminal.exe'})

@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


def classify(title: str, exe: str) -> Decision:
    if not title.strip() or not exe.strip():
        return Decision(False,'Window identity could not be established')
    if DENY.search(title+' '+exe):
        return Decision(False,'Sensitive window context is blocked')
    if exe.casefold() in DENY_EXES:
        return Decision(False,'Sensitive application is blocked')
    if exe.casefold() in BROWSER_EXES or BROWSER_TITLE.search(title):
        return Decision(False,'Browser content requires a separately isolated protected browser controller')
    return Decision(True,'Foreground non-browser window eligible for one-shot capture')


def inspect_foreground() -> dict:
    """Get foreground window metadata. Never returns its pixels or content."""
    import ctypes
    from ctypes import wintypes
    try:
        import psutil
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return {'status':'blocked','reason':'No foreground window'}
        length=user32.GetWindowTextLengthW(hwnd)
        title=ctypes.create_unicode_buffer(length+1)
        user32.GetWindowTextW(hwnd,title,length+1)
        pid=wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        exe=psutil.Process(pid.value).name()
        decision=classify(title.value,exe)
        # Don't reveal blocked titles (can contain sensitive content).
        if not decision.allowed:
            return {'status':'blocked','reason':decision.reason}
        return {'status':'eligible','title':title.value,'process':exe,'reason':decision.reason}
    except Exception as exc:
        return {'status':'blocked','reason':'Window inspection unavailable: '+type(exc).__name__}


def normalize_english(transcript: str) -> str:
    """Leave transcript unchanged. Never silently transliterate/transcribe user audio."""
    return transcript


def is_explicit_screen_request(transcript: str) -> bool:
    text=(transcript or '').casefold()
    # Permission questions should not create a screenshot.
    if re.search(r'\b(can you|are you able|do you have (?:access|permission))\b', text):
        return False
    return bool(re.search(r'\b(?:inspect|look at|read|analy[sz]e|show|describe|check)\b.{0,60}\b(?:screen|window|display|notepad|app)\b',text))
