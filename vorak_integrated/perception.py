"""Ephemeral, user-requested visual input; no image files, no background capture.

Images go only to the active Gemini Live connection. Fail closed on unknown or
protected active windows. Web pages/browsers cannot be certified by window title.
"""
from __future__ import annotations
from io import BytesIO
import os

from vorak_integrated import screen_access
from vorak_integrated.trust_policy import denied_name

MAX_IMAGE_BYTES=2_600_000


def _jpeg(image, long_edge=1440):
    image.thumbnail((long_edge, long_edge))
    out=BytesIO()
    image.convert('RGB').save(out,format='JPEG',quality=78,optimize=True)
    data=out.getvalue()
    if not data or len(data)>MAX_IMAGE_BYTES:
        raise ValueError('Image size invalid')
    return data


def screen_frame(scope='work', snapshot=None, grab=None):
    """Capture active app or Windows desktop, preserving process and window identity.

    EnumWindows returns z-order (front to back). Only overlapping windows in front
    of the selected foreground window can contaminate an active-window crop.
    The browser itself always fails closed: title checks cannot rule out payments.
    """
    if scope not in ('work','desktop'):
        return None,'Unsupported screen scope.'
    snap=snapshot or screen_access._windows_snapshot
    try:
        fg, windows=snap()
        allowed,reason=screen_access.policy(fg.title,fg.executable)
        if not allowed:
            return None,reason
        if scope=='desktop' and fg.executable.casefold()!='explorer.exe':
            return None,'Desktop capture requires showing the Windows desktop (Win+D).'
        if denied_name(fg.title+' '+fg.executable):
            return None,'Protected app or payment context detected.'
        if fg.hwnd not in [w.hwnd for w in windows]:
            return None,'Foreground app not verified.'
        fg_i=next(i for i,w in enumerate(windows) if w.hwnd==fg.hwnd)
        if grab is None:
            from PIL import ImageGrab
            grab=ImageGrab.grab
        if scope == 'work':
            # Pillow on Windows can capture a specific HWND, without overlay leakage.
            # Do NOT fall back to grabbing a desktop rectangle (it may reveal overlays).
            try:
                image=grab(window=fg.hwnd)
            except (TypeError, OSError, ValueError):
                return None,'Direct window capture unavailable. Update Pillow or select another app.'
        else:
            # Desktop is the only scope where overlays matter and full display is read.
            for w in windows[:fg_i]:
                if screen_access.intersects(w.rect,fg.rect):
                    return None,'Protected overlay may be visible on the desktop; blocked.'
            image=grab(bbox=None,all_screens=False)
        fg2,windows2=snap()
        if (fg.hwnd,fg.title,fg.executable,fg.rect)!=(fg2.hwnd,fg2.title,fg2.executable,fg2.rect):
            return None,'Foreground window changed; discarded screenshot.'
        if scope=='desktop':
            try:
                index2=next(i for i,w in enumerate(windows2) if w.hwnd==fg2.hwnd)
            except StopIteration:
                return None,'Desktop window disappeared during capture.'
            if [w.hwnd for w in windows[:fg_i]] != [w.hwnd for w in windows2[:index2]]:
                return None,'Window stacking changed; discarded screenshot.'
        return _jpeg(image), f'Captured active {fg.executable} window.' if scope=='work' else 'Captured Windows desktop.'
    except Exception as e:
        return None,'Screen unavailable: '+type(e).__name__


def camera_frame(index=0, camera_factory=None):
    """Capture three frames for exposure settling and release camera on every path.
    CLAHE slightly improves document legibility without claiming torch hardware.
    """
    if not isinstance(index,int) or not 0<=index<=4:
        return None,'Invalid camera index.'
    camera=None
    try:
        import cv2
        factory=camera_factory or (lambda ix: cv2.VideoCapture(ix,cv2.CAP_DSHOW if os.name=='nt' else cv2.CAP_ANY))
        camera=factory(index)
        if not camera.isOpened():
            return None,'Camera unavailable or blocked by Windows privacy settings.'
        camera.set(cv2.CAP_PROP_FRAME_WIDTH,1280)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT,720)
        frame=None
        for _ in range(5):
            ok,pic=camera.read()
            if ok and pic is not None:frame=pic
        if frame is None:
            return None,'No camera image received.'
        # Controlled luminance improvement; no face recognition or recording.
        lab=cv2.cvtColor(frame,cv2.COLOR_BGR2LAB)
        l,a,b=cv2.split(lab)
        l=cv2.createCLAHE(clipLimit=1.8,tileGridSize=(8,8)).apply(l)
        enhanced=cv2.cvtColor(cv2.merge((l,a,b)),cv2.COLOR_LAB2BGR)
        ok,jpg=cv2.imencode('.jpg',enhanced,[cv2.IMWRITE_JPEG_QUALITY,78])
        if not ok or jpg.nbytes>MAX_IMAGE_BYTES:
            return None,'Camera JPEG encoding failed.'
        return jpg.tobytes(),'Camera frame captured. Use a room light for paper; most laptop webcams have no controllable torch.'
    except Exception as exc:
        return None,'Camera unavailable: '+type(exc).__name__
    finally:
        if camera is not None:
            try:camera.release()
            except Exception:pass


async def send_visual(session, source, *, question='', screen_fn=None, camera_fn=None):
    """Send one JPEG through the *working* Gemini Live session, no second vision model.
    The caller must invoke this solely upon a direct owner request.
    """
    if source not in {'work','desktop','camera'}:
        return {'status':'blocked','message':'Unknown visual source.'}
    image,note=((camera_fn or camera_frame)() if source=='camera' else
                (screen_fn or screen_frame)(source))
    if image is None:
        return {'status':'blocked','message':note}
    from google.genai import types
    try:
        await session.send_realtime_input(video=types.Blob(data=image,mime_type='image/jpeg'))
        return {'status':'frame_delivered','message':note+' Image provided to current Gemini Live session.',
                'question':str(question)[:160]}
    except Exception as e:
        return {'status':'failed','message':'Gemini Live image transfer failed: '+type(e).__name__}
