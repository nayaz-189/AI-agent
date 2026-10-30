"""VORAK verified WhatsApp Message Yourself workflow.

Window first, launch only if missing. Never guesses contacts, sends only on
an independent explicit-send route and only after exact composer verification.
"""
from __future__ import annotations
import re
import time


def self_message(text: str, send=False, *, draft=None, verify=None, sleep=time.sleep):
    if not isinstance(text,str) or not 1 <= len(text) <= 500 or any(ord(c)<32 for c in text):
        return {'status':'blocked','message':'Invalid WhatsApp text.'}
    if send is True:
        return {'status':'blocked','message':'Sending requires separate owner verification; this voice session can only draft.'}
    if re.search(r'(?i)\b(?:otp|password|credit card|debit card|bank transfer|upi pin)\b',text):
        return {'status':'blocked','message':'Sensitive content cannot be drafted.'}
    try:
        if draft is None:
            from vorak_integrated import whatsapp_self
        prepare=draft or whatsapp_self.prepare_self_draft
        checker=verify or (whatsapp_self._verified_self_chat if draft is None else None)
        win=None
        if draft is None:
            try:win=whatsapp_self._window()
            except Exception:win=None
            if win is None:
                from vorak_integrated.actions import open_target
                launched=open_target('WhatsApp',confirm=None)
                if launched.get('status') not in {'dispatched','opened'}:
                    return {'status':'not_ready','message':'WhatsApp was not launched: '+str(launched.get('status'))}
                until=time.monotonic()+7.0
                while time.monotonic()<until:
                    try:win=whatsapp_self._window()
                    except Exception:win=None
                    if win is not None:break
                    sleep(.2)
            if win is None:
                return {'status':'not_ready','message':'WhatsApp launched, but no verifiable Desktop window was found.'}
            result=prepare(text,window=win)
        else:result=prepare(text)
        if not isinstance(result,dict):
            return {'status':'failed','message':'Invalid WhatsApp action result.'}
        if result.get('status')!='drafted' or not send:
            return result
        if draft is not None:
            return {'status':'blocked','message':'Injected draft requires independent verification before Send.'}
        win=whatsapp_self._window()
        if win is None:
            return {'status':'drafted','message':'Draft exists, but self-chat could not be reverified. Not sent.'}
        composer=checker(win)
        if composer is None:
            return {'status':'drafted','message':'Self-chat header not reverified. Not sent.'}
        try: value=composer.get_value()
        except Exception:value=None
        if not isinstance(value,str) or value.strip()!=text.strip():
            return {'status':'drafted','message':'Draft exact text not verified. Not sent.'}
        if checker(win) is None:
            return {'status':'drafted','message':'Chat changed before sending. Not sent.'}
        composer.set_focus()
        composer.type_keys('{ENTER}')
        return {'status':'send_attempted','message':'Send key attempted in independently verified self-chat. Delivery not verified.'}
    except Exception as exc:
        return {'status':'failed','message':'WhatsApp operation failed: '+type(exc).__name__+'.'}
