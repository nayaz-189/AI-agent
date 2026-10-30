"""Window-only PrintWindow fallback, never a desktop or screen rectangle capture.

Only call after screen_focus has approved the exact HWND and PID.  This backend
can still fail for hardware-accelerated Electron windows; it does not bypass
Windows display protections or your application's privacy policy.
"""
from __future__ import annotations
import ctypes


def capture_hwnd(hwnd: int):
    import win32gui
    import win32ui
    from PIL import Image

    if not isinstance(hwnd, int) or hwnd <= 0 or not win32gui.IsWindow(hwnd):
        return None
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width, height = right - left, bottom - top
    if not 80 <= width <= 5500 or not 60 <= height <= 4200:
        return None
    window_dc = win32gui.GetWindowDC(hwnd)
    if not window_dc:
        return None
    src = mem = bitmap = None
    try:
        src = win32ui.CreateDCFromHandle(window_dc)
        mem = src.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(src, width, height)
        mem.SelectObject(bitmap)
        # PW_RENDERFULLCONTENT (2). Does NOT composite other windows/monitors.
        success = ctypes.windll.user32.PrintWindow(hwnd, mem.GetSafeHdc(), 2)
        if success != 1:
            return None
        bits = bitmap.GetBitmapBits(True)
        result = Image.frombuffer('RGB', (width, height), bits, 'raw', 'BGRX', 0, 1).copy()
        return result
    finally:
        if mem is not None:
            try: mem.DeleteDC()
            except Exception: pass
        if bitmap is not None:
            try: win32gui.DeleteObject(bitmap.GetHandle())
            except Exception: pass
        if src is not None:
            try: src.DeleteDC()
            except Exception: pass
        win32gui.ReleaseDC(hwnd, window_dc)


def image_is_blank(image) -> bool:
    if image is None:
        return True
    try:
        from PIL import ImageStat
        if image.width < 80 or image.height < 60:
            return True
        sample = image.copy()
        sample.thumbnail((360, 360))
        stats = ImageStat.Stat(sample.convert('L'))
        return stats.stddev[0] < 0.9
    except Exception:
        return True
