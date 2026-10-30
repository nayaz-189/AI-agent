"""Targeted read-only Windows window capture for VORAK Gemini Live.

Explicit user command only. Never captures browser, payments, or credential apps.
Pillow ImageGrab.grab(window=HWND) captures an individual window, not an
unrestricted rectangular desktop crop. No screenshots are persisted by default.
"""
from __future__ import annotations

import argparse
import io
import os
import re
from dataclasses import dataclass

MAX_JPEG = 2_600_000
MAX_EDGE = 1600
ALIASES = {
    'notepad': ('notepad.exe',),
    'visual studio code': ('code.exe',),
    'vs code': ('code.exe',),
    'vscode': ('code.exe',),
    'whatsapp': ('whatsapp.exe', 'whatsappdesktop.exe'),
}
SKIP_GENERIC = ('screen', 'desktop', 'window', 'app', 'application', 'right now', 'currently', 'work', 'current')


def requested_name(text: str) -> str:
    """Extract explicit application hint; never infer a protected app."""
    raw = (text or '').casefold().strip()
    if raw in SKIP_GENERIC or raw in {'my screen', 'my desktop', 'my window', 'my work screen', 'current window'}:
        return ''
    if not raw:
        return ''
    for alias in sorted(ALIASES, key=len, reverse=True):
        if re.search(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', raw):
            return alias
    # Explicit short target from the model, not an entire question.
    if len(raw) < 60 and not any(k in raw for k in (
            'look', 'inspect', 'describe', 'read', 'tell me', 'what ', 'can you', '?')):
        return raw
    return ''


def _choices(windows, query):
    q = requested_name(query)
    if not q:
        return []
    allowed_exes = ALIASES.get(q, ())
    return [w for w in windows if (w.executable.casefold() in allowed_exes or
           (len(q) >= 4 and q in w.title.casefold()))]


def pick_window(foreground, windows, target):
    """If a target is specified, resolve that exact displayed app; otherwise foreground.

    Refuses an ambiguous match rather than picking an unrelated chat/window.
    """
    from vorak_integrated.screen_access import policy
    q = requested_name(target)
    if q:
        candidates = [w for w in _choices(windows, q) if policy(w.title, w.executable)[0]]
        if not candidates:
            return None, 'Target application was not found among eligible visible windows.'
        if len(candidates) > 1:
            # When several windows have the name, foreground is an unambiguous choice.
            if any(w.hwnd == foreground.hwnd for w in candidates):
                chosen = next(w for w in candidates if w.hwnd == foreground.hwnd)
            else:
                return None, 'Several eligible windows match; focus the intended one or close duplicates.'
        else:
            chosen = candidates[0]
    else:
        chosen = foreground
    okay, reason = policy(chosen.title, chosen.executable)
    if not okay:
        return None, reason
    if chosen.rect[2] <= chosen.rect[0] or chosen.rect[3] <= chosen.rect[1]:
        return None, 'Invalid window dimensions.'
    return chosen, ''


def capture_work_window(target='', *, snapshot=None, grab=None):
    """Return (JPEG bytes, capture note) or (None, a diagnostic message).

    A current user utterance requesting vision is the only entry point in Live.
    Windows identity is checked both before and after acquisition. Captured
    pixels stay in memory and are sent only to the already active Live session.
    """
    try:
        from vorak_integrated import screen_access
        snap = snapshot or screen_access._windows_snapshot
        first, visible = snap()
        w, reason = pick_window(first, visible, target)
        if w is None:
            return None, reason
        if grab is None:
            from PIL import ImageGrab
            grab = ImageGrab.grab
        # VORAK_FOCUS_FIX_V6: Both backends capture ONLY the validated HWND.
        # Never capture a desktop rectangle, browser or another application's pixels.
        from vorak_integrated.hwnd_capture import capture_hwnd, image_is_blank
        try:
            image = grab(window=w.hwnd)
        except Exception:
            image = None
        if image_is_blank(image):
            # PrintWindow sometimes handles Electron/VS Code better than Pillow.
            # It does not override Windows protected content or allow browser capture.
            try: image = capture_hwnd(w.hwnd)
            except Exception: image = None
        second, visible2 = snap()
        matching = next((v for v in visible2 if v.hwnd == w.hwnd), None)
        if not matching or (w.title, w.executable, w.rect) != (matching.title, matching.executable, matching.rect):
            return None, 'Window identity changed while capturing; image discarded.'
        allowed, why = screen_access.policy(matching.title, matching.executable)
        if not allowed:
            return None, 'Window became protected during capture: '+why
        if image is None or image.width < 80 or image.height < 60:
            return None, 'Window image is blank or unavailable.'
        from PIL import ImageStat
        scaled = image.copy()
        scaled.thumbnail((MAX_EDGE, MAX_EDGE))
        stat = ImageStat.Stat(scaled.convert('L'))
        if stat.stddev[0] < 0.9:
            return None, 'Window image is uniform/blank; the app may not support HWND capture.'
        out = io.BytesIO()
        scaled.convert('RGB').save(out, 'JPEG', quality=80, optimize=True)
        result = out.getvalue()
        if len(result) > MAX_JPEG or not result:
            return None, 'Window image is outside the allowed size.'
        return result, f'Captured {w.executable}: {w.title[:80]} (HWND-only, no overlapping windows).'
    except Exception as e:
        return None, 'Targeted window capture failed: '+type(e).__name__


def main(argv=None):
    parser = argparse.ArgumentParser(description='VORAK safe Windows window capture test (no Gemini API call)')
    parser.add_argument('--target', default='', help='Visible app name, e.g. Notepad or VS Code')
    parser.add_argument('--list', action='store_true', help='List eligible visible windows without capture')
    parser.add_argument('--output', default='', help='Optional local JPEG to visually verify an eligible window; omit to keep in memory')
    args = parser.parse_args(argv)
    from vorak_integrated.screen_access import _windows_snapshot, policy
    if os.name != 'nt':
        parser.error('This command runs on Windows only.')
    fg, windows = _windows_snapshot()
    if args.list:
        for w in windows:
            if policy(w.title, w.executable)[0]:
                print(f'[{w.hwnd}] {w.executable} | {w.title[:90]}')
        return 0
    data, note = capture_work_window(args.target)
    print(note)
    if not data:
        return 1
    print(f'SAFE WINDOW CAPTURE OK: {len(data)} bytes, held only in RAM')
    if args.output:
        from pathlib import Path
        p = Path(args.output).expanduser().resolve()
        if p.suffix.lower() not in {'.jpg', '.jpeg'}:
            parser.error('--output must end in .jpg or .jpeg')
        if p.exists():
            parser.error('Refusing to overwrite existing image')
        p.write_bytes(data)
        print('Local preview saved:', p)
        print('Remove it after inspecting; the image may contain private app content.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
