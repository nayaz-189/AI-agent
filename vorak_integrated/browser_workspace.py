"""Playwright isolated browser worker with URL, form, and action boundary checks.
Never attaches to a personal Chrome profile; never accesses banking, login or checkout.
"""
from __future__ import annotations
import atexit
import ipaddress
import queue
import re
import threading
from urllib.parse import urlsplit

BLOCKED_UI = re.compile(r'(?i)\b(?:password|otp|2fa|checkout|billing|payment|pay now|purchase|place order|bank|transfer|login|log in|sign in|credit card|debit card)\b')
BLOCKED_ACTION = re.compile(r'(?i)\b(?:send|submit|publish|post|share|upload|delete|remove|invite|buy|purchase|pay|checkout|login|log in|sign in|password|otp|transfer|bank)\b')
HIGH_RISK_VISIBLE = re.compile(r'(?i)\b(?:payment details|enter your password|card number|confirm purchase|complete payment|enter otp|enter your pin)\b')
PUBLIC_ACTIONS = {'open','inspect','click','fill'}


def safe_url(url):
    from vorak_integrated.trust_policy import denied_url
    if not isinstance(url,str) or len(url)>2048 or '\\' in url or any(ord(c)<32 for c in url):return False
    try:
        p=urlsplit(url)
        hostname=(p.hostname or '').casefold().rstrip('.')
        if not hostname or p.username is not None or p.password is not None:return False
        if p.scheme not in {'https','http'}:return False
        if p.scheme=='http' and hostname not in {'localhost','127.0.0.1','[::1]','::1'}:return False
        try:
            address=ipaddress.ip_address(hostname)
            if not address.is_loopback:return False
        except ValueError:
            if hostname in {'localhost','localhost.localdomain'}:pass
            elif '.' not in hostname or hostname.endswith(('.local','.internal','.test')):return False
        if denied_url(url) or BLOCKED_UI.search((p.path or '').replace('-',' ')) or BLOCKED_UI.search(hostname.replace('-',' ')):
            return False
        return True
    except (TypeError,ValueError):return False


def _protected_page(page):
    try:
        if not safe_url(page.url):return True
        if BLOCKED_UI.search(page.title() or ''):return True
        if page.locator('input[type="password"], input[autocomplete="one-time-code"], input[autocomplete="cc-number"]').count():return True
        # Hidden embedded login or payment frames block access as well.
        for frame in page.frames:
            if frame == page.main_frame:continue
            if frame.url != 'about:blank' and not safe_url(frame.url):return True
            if frame.locator('input[type="password"], input[autocomplete="one-time-code"], input[autocomplete="cc-number"]').count():return True
        return False
    except Exception:return True


def execute(page, action, *, url='',role='',name='',text=''):
    """Perform a single verified step; tests can inject a fake Playwright page."""
    if action not in PUBLIC_ACTIONS:return {'status':'blocked','message':'Unknown browser action.'}
    if any(not isinstance(x,str) for x in (url,role,name,text)) or len(name)>150 or len(text)>1000:
        return {'status':'blocked','message':'Invalid browser arguments.'}
    if action=='open':
        if not safe_url(url):return {'status':'blocked','message':'Unsafe or protected website URL.'}
        try:
            page.goto(url,wait_until='domcontentloaded',timeout=15000)
            if _protected_page(page):
                page.goto('about:blank')
                return {'status':'blocked','message':'Destination resolved to a protected page; content withheld.'}
            return {'status':'opened','url':page.url,'title':page.title()[:120]}
        except Exception as exc:return {'status':'failed','message':'Navigation failed: '+type(exc).__name__}
    if _protected_page(page):return {'status':'blocked','message':'Protected browser page; no inspection or action.'}
    if action=='inspect':
        try:
            raw=page.locator('body').inner_text(timeout=3500)
            if HIGH_RISK_VISIBLE.search(raw[:1200]):
                return {'status':'blocked','message':'Sensitive payment or credential content detected; withheld.'}
            return {'status':'observed','url':page.url,'title':page.title()[:120],
                    'content':' '.join(raw.split())[:2500],
                    '_frame':page.screenshot(type='jpeg',quality=65,full_page=False)}
        except Exception as exc:return {'status':'failed','message':'Page inspection failed: '+type(exc).__name__}
    if role not in {'button','link','textbox','searchbox','checkbox','tab'} or not name.strip() or BLOCKED_ACTION.search(name):
        return {'status':'blocked','message':'A safe accessible role and exact control name are required.'}
    if action=='fill' and (role not in {'textbox','searchbox'} or not text or any(ord(c)<32 for c in text)):
        return {'status':'blocked','message':'Fill requires a named text field and a printable value.'}
    if action=='click' and role not in {'button','link','tab','checkbox'}:
        return {'status':'blocked','message':'Unsupported click role.'}
    try:
        locator=page.get_by_role(role,name=name,exact=True)
        if locator.count()!=1:return {'status':'not_ready','message':'Named control missing or ambiguous.'}
        if action=='fill':
            locator.fill(text,timeout=4500)
            if _protected_page(page):return {'status':'blocked','message':'Page became protected after entry; stop.'}
            value=locator.input_value()
            return {'status':'verified' if value==text else 'attempted_unverified','message':'Field updated.'}
        locator.click(timeout=4500)
        if _protected_page(page):
            page.goto('about:blank')
            return {'status':'blocked','message':'Action led to a protected page; workspace cleared.'}
        return {'status':'attempted_unverified','message':'Clicked control; check page state with inspect.',
                'url':page.url}
    except Exception as exc:return {'status':'failed','message':'Browser control failed: '+type(exc).__name__}


class BrowserWorker:
    def __init__(self):
        self._jobs=queue.Queue(maxsize=10)
        self._thread=None
        self._lock=threading.Lock()

    def _loop(self):
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                # Separate ephemeral Chromium workspace. Does not inherit the
                # user's logged-in Chrome/Firefox/Opera or stored credentials.
                browser=pw.chromium.launch(headless=False)
                context=browser.new_context(accept_downloads=False,permissions=[])
                page=context.new_page()
                try:
                    while True:
                        result,args=self._jobs.get()
                        if args is None:
                            result.put({'status':'closed'})
                            break
                        try: result.put(execute(page,**args),timeout=1)
                        except Exception as exc:result.put({'status':'failed','message':type(exc).__name__})
                finally:
                    context.close();browser.close()
        except Exception as exc:
            # If launch failed, give every waiting request a concrete result.
            while True:
                try:result,_=self._jobs.get_nowait()
                except queue.Empty:break
                result.put({'status':'failed','message':'Playwright browser unavailable: '+type(exc).__name__})
            with self._lock:self._thread=None

    def close(self):
        with self._lock:
            thread=self._thread
        if thread is None or not thread.is_alive():return
        reply=queue.Queue(maxsize=1)
        try:
            self._jobs.put_nowait((reply,None))
            thread.join(timeout=3)
        except queue.Full:pass

    def act(self,action='inspect',url='',role='',name='',text=''):
        if action not in PUBLIC_ACTIONS:return {'status':'blocked','message':'Invalid browser action.'}
        if action=='open' and not safe_url(url):return {'status':'blocked','message':'Protected website.'}
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread=threading.Thread(target=self._loop,name='VORAK-safe-browser',daemon=True)
                self._thread.start()
        result=queue.Queue(maxsize=1)
        try:
            self._jobs.put((result,dict(action=action,url=url,role=role,name=name,text=text)),timeout=1)
            return result.get(timeout=22)
        except queue.Empty:return {'status':'timeout','message':'Browser operation did not finish.'}
        except queue.Full:return {'status':'busy','message':'Browser task queue full.'}


_WORKER=BrowserWorker()
atexit.register(_WORKER.close)

def act(action='inspect',url='',role='',name='',text=''):
    return _WORKER.act(action,url,role,name,text)
