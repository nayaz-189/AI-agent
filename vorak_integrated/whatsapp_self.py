"""VORAK WhatsApp Desktop: locate self-chat using verified Windows UIA controls.

DRAFT ONLY. No arbitrary chat message, send, coordinate or clipboard actions.
All interactions are visible in the WhatsApp app itself.
"""
from __future__ import annotations
import re
import time

MESSAGE = "Hi, I'm VORAK. This is my first message."
SELF = {'message yourself', 'message yourself (you)', 'you (self)', 'yourself'}
SEARCH_LABELS = ('search', 'find a chat', 'start a chat', 'search or start')
COMPOSE_LABELS = ('type a message', 'message input', 'write a message', 'enter a message')


def _text(el):
    try: return str(el.window_text() or '').strip()
    except Exception: return ''


def _kind(el):
    try: return str(el.element_info.control_type or '').strip()
    except Exception: return ''


def _aid(el):
    try: return str(el.element_info.automation_id or '').strip()
    except Exception: return ''


def _norm(value):
    return ' '.join(str(value).casefold().split())


def _self_indicator(s):
    label=_norm(s)
    return label in SELF or label.endswith(' (you)')


def _rect(node):
    try:
        r=node.rectangle(); return (int(r.left),int(r.top),int(r.right),int(r.bottom))
    except Exception:return None


def _region(win, e, *, right=False, top=False, bottom=False):
    frame=_rect(win);part=_rect(e)
    if not frame or not part:return False
    l,t,r,b=frame;x,y,x2,y2=part
    width=r-l;height=b-t
    if width<440 or height<310 or x2<=x or y2<=y:return False
    cx=(x+x2)/2;cy=(y+y2)/2
    if not (l<=cx<=r and t<=cy<=b):return False
    if right and cx < l + width*.43:return False
    if top and not(t+height*.005 <=cy<= t+height*.25):return False
    if bottom and not(t+height*.64 <=cy<= b-height*.005):return False
    return True


def _belongs_to_chat_header(el):
    current=el
    for _ in range(6):
        if current is None:break
        label=_norm(_aid(current))+' '+_norm(_text(current))
        if any(token in label for token in ('chatheader','chat header','conversationheader','chat-header')):
            return True
        try:current=current.parent()
        except Exception:break
    return False


def _controls(win):
    try:return win.descendants()[:450]
    except Exception:return []


def _verified_self_chat(win):
    """Confirm chat header on RIGHT TOP and composer on RIGHT BOTTOM.

    Sidebar search results do not satisfy verification. Avoid all guesses based
    solely on the word 'You' in a searchable contact list.
    """
    elements=_controls(win)
    headers=[]
    for el in elements:
        if not _self_indicator(_text(el)) or _kind(el) not in {'Text','Button','Group','DataItem','ListItem'}:continue
        if _region(win,el,right=True,top=True) or (_belongs_to_chat_header(el) and _region(win,el,right=True)):
            headers.append(el)
    if not headers:return None
    candidates=[]
    for el in elements:
        if _kind(el) not in {'Edit','Document'}:continue
        label=_norm(_text(el)+' '+_aid(el))
        if any(x in label for x in SEARCH_LABELS):continue
        is_message=any(x in label for x in COMPOSE_LABELS)
        if _region(win,el,right=True,bottom=True):
            candidates.append((1 if is_message else 0,el))
    if not candidates:return None
    named=[node for score,node in candidates if score]
    if len(named)==1:return named[0]
    # Anonymous rich-text Document can still be the composer if UNIQUE.
    if len(named)==0 and len(candidates)==1:return candidates[0][1]
    return None


def _search_box(win):
    elements=_controls(win)
    matches=[e for e in elements if _kind(e) in {'Edit','Document'} and
             any(x in _norm(_text(e)+' '+_aid(e)) for x in SEARCH_LABELS)]
    return matches[0] if len(matches)==1 else None


def _send_safe_text(el, value):
    # `type_keys` treats braces, ^, %, +, ~ as shortcut metacharacters.
    # Reject those rather than turn user text into keyboard commands.
    if re.search(r'[{}^%+~\[\]]',value):
        raise ValueError('Unsupported keyboard-special characters; draft not entered.')
    el.set_focus()
    try:el.set_edit_text(value)
    except (AttributeError,NotImplementedError,RuntimeError,ValueError,TypeError):
        el.type_keys(value,with_spaces=True,set_foreground=True,vk_packet=True)


def _select_self_chat(win):
    search=_search_box(win)
    if search is None:return False,'WhatsApp chat search field was not uniquely identified.'
    try:
        from pywinauto.keyboard import send_keys
        search.set_focus();send_keys('^a')
        # Simulated keystrokes trigger search events in WebView-backed UIs.
        search.type_keys('Message yourself',with_spaces=True,set_foreground=True,vk_packet=True)
    except Exception as exc:
        return False,'Could not enter self-chat search: '+type(exc).__name__
    # Poll for search results; do not depend on fixed seconds of sleeping.
    until=time.monotonic()+3.0
    while time.monotonic()<until:
        elements=_controls(win)
        hits=[e for e in elements if _self_indicator(_text(e)) and
              _kind(e) in {'Text','ListItem','Button','DataItem'} and
              not _region(win,e,right=True,top=True)]
        # Repeated/ambiguous labels must not select the wrong chat.
        if len(hits)==1:
            hits[0].click_input()
            settle=time.monotonic()+3.0
            while time.monotonic()<settle:
                if _verified_self_chat(win) is not None:
                    return True,'Verified Message Yourself conversation is active.'
                time.sleep(.15)
            return False,'Self-chat clicked, but conversation header/composer not verified.'
        time.sleep(.15)
    return False,'Could not identify a unique Message Yourself result.'


def _window():
    """Accept only a genuine WhatsApp Desktop window or a WhatsApp-marked packaged host."""
    import psutil
    from pywinauto import Desktop
    matches=[]
    for win in Desktop(backend='uia').windows(visible_only=True):
        try:
            proc=psutil.Process(win.element_info.process_id)
            name=proc.name().casefold()
            exe=proc.exe().casefold()
        except (psutil.Error,OSError,ValueError):continue
        titled='whatsapp' in _norm(_text(win))
        direct=name in {'whatsapp.exe','whatsappdesktop.exe'} or 'whatsappdesktop' in exe
        host=name in {'applicationframehost.exe','msedgewebview2.exe'}
        if not direct and not host:continue
        if host:
            # UWP outer host may have no title. Require a WhatsApp-labelled UI
            # or an actual descendant process in the WhatsApp package.
            controls=_controls(win)[:100]
            labels=[_norm(_text(e)+' '+_aid(e)) for e in controls]
            branded=any('whatsapp' in label for label in labels)
            child_package=False
            if not branded:
                for child in controls:
                    try:
                        sub=psutil.Process(child.element_info.process_id)
                        if ('whatsappdesktop' in sub.exe().casefold() or
                            sub.name().casefold() in {'whatsapp.exe','whatsappdesktop.exe'}):
                            child_package=True;break
                    except (psutil.Error,OSError,ValueError,AttributeError):continue
            if not (branded or child_package):continue
        matches.append((int(bool(titled)),win))
    if not matches:return None
    best=max(x[0] for x in matches)
    strongest=[w for priority,w in matches if priority==best]
    return strongest[0] if len(strongest)==1 else None


def prepare_self_draft(message=MESSAGE, *,window=None,select_fn=None):
    if not isinstance(message,str) or not 1<=len(message)<=500 or any(ord(c)<32 for c in message):
        return {'status':'blocked','message':'Invalid WhatsApp draft.'}
    if re.search(r'[{}^%+~\[\]]',message):
        return {'status':'blocked','message':'Draft contains keyboard-special characters; nothing typed.'}
    try:
        win=window or _window()
        if win is None:return {'status':'not_ready','message':'No uniquely verified WhatsApp Desktop window.'}
        win.set_focus()
        composer=_verified_self_chat(win)
        if composer is None:
            selected,why=(select_fn or _select_self_chat)(win)
            if not selected:return {'status':'not_ready','message':why}
            composer=_verified_self_chat(win)
        if composer is None:return {'status':'blocked','message':'Self-chat header/composer not verified. Nothing typed.'}
        if _verified_self_chat(win) is None:
            return {'status':'blocked','message':'Chat changed. Nothing typed.'}
        try: existing=str(composer.get_value() or '').strip()
        except Exception:existing=''
        if existing and existing!=message.strip():
            return {'status':'not_ready','message':'The verified self-chat already contains a different draft; nothing overwritten.'}
        if existing==message.strip():
            return {'status':'drafted','message':'Exact text already exists in Message Yourself composer. Not sent.'}
        _send_safe_text(composer,message)
        try: value=str(composer.get_value() or '')
        except Exception:value=''
        if value.strip()==message.strip():
            return {'status':'drafted','message':'Exact text verified in Message Yourself composer. Not sent.'}
        return {'status':'attempted_unverified','message':'Typed in verified self-chat but could not read back composer text. Check the visible draft. Not sent.'}
    except Exception as exc:
        return {'status':'failed','message':'Self-chat draft failed: '+type(exc).__name__+'. No Send attempted.'}


def diagnostic():
    """Only local summary of control types and safe labels. No contacts, chat messages or screenshots."""
    win=_window()
    if win is None:return {'status':'not_ready','message':'WhatsApp Desktop window not uniquely verified.'}
    els=_controls(win)
    roles={}
    for e in els:
        kind=_kind(e)
        roles[kind]=roles.get(kind,0)+1
    return {'status':'observed','window_found':True,'control_count':len(els),
            'roles':dict(sorted(roles.items())),'self_header_and_composer':_verified_self_chat(win) is not None,
            'search_found':_search_box(win) is not None}
