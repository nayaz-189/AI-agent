"""Windows UI Automation for an explicitly requested, verified, unprotected application.
Never coordinate-click or run shell commands; every action binds to an HWND and an exact UIA control.
"""
from __future__ import annotations
import re

MAX_ELEMENTS = 350
INTERACTIVE = {'Edit', 'Document', 'Button', 'Hyperlink', 'TabItem', 'ListItem', 'MenuItem', 'ComboBox', 'CheckBox'}
FILL_ROLES = {'Edit', 'Document'}
CLICK_ROLES = INTERACTIVE - FILL_ROLES
DANGEROUS = re.compile(r'(?i)\b(?:delete|remove account|buy|send|submit|publish|post|share|upload|pay|purchase|checkout|billing|bank|sign in|log in|login|password|otp|two.factor|transfer|send money|subscribe|unsubscribe|confirm payment|place order|submit order|reveal secret|send message)\b')


def _name(node):
    try: return str(node.window_text() or '').strip()
    except Exception: return ''


def _role(node):
    try: return str(node.element_info.control_type or '').strip()
    except Exception: return ''


def _aid(node):
    try: return str(node.element_info.automation_id or '').strip()
    except Exception: return ''


def _scrub(value):
    if DANGEROUS.search(value):
        return '[protected control]'
    return value[:100]


def _selected(target, snapshot):
    from vorak_integrated.screen_focus import pick_window
    from vorak_integrated.screen_access import policy
    foreground, windows = snapshot()
    chosen, why = pick_window(foreground, windows, target or '')
    if chosen is None: return None, why
    allowed, why = policy(chosen.title, chosen.executable)
    if not allowed: return None, why
    # Chrome, Edge, Firefox etc are browser contexts, to be handled with
    # browser_workspace URL/DOM guards; generic UIA cannot prove payment state.
    if chosen.executable.casefold() in {'chrome.exe','msedge.exe','firefox.exe','opera.exe','brave.exe'}:
        return None, 'Browser UI is only accessible via the protected browser workspace.'
    return chosen, ''


def _resolve(elements, identity, allowed):
    key=(identity or '').strip().casefold()
    if not key: return None,'A named control is required for this action.'
    matches=[e for e in elements if _role(e) in allowed and
             (key == _name(e).casefold() or key == _aid(e).casefold())]
    if len(matches) == 1: return matches[0], ''
    return None,('Control not found.' if not matches else 'Control is ambiguous; nothing changed.')


def act(action='inspect', target='', control='', text='', *, snapshot=None, desktop=None):
    """Return verified UI results. The model cannot authorize broad desktop input."""
    if action not in {'inspect','click','fill'}: return {'status':'blocked','message':'Unsupported app action.'}
    if any(not isinstance(x,str) for x in (target,control,text)) or len(target)>100 or len(control)>100 or len(text)>1000:
        return {'status':'blocked','message':'Invalid action parameters.'}
    if action!='inspect' and (DANGEROUS.search(control) or DANGEROUS.search(target)):
        return {'status':'blocked','message':'Protected or consequential action is not available.'}
    if action=='fill' and (not text or any(ord(c)<32 for c in text)):
        return {'status':'blocked','message':'Fill text must be a single printable line.'}
    try:
        if snapshot is None:
            from vorak_integrated.screen_access import _windows_snapshot
            snapshot=_windows_snapshot
        snap=snapshot
        chosen,why=_selected(target,snap)
        if chosen is None: return {'status':'blocked','message':why}
        if desktop is None:
            from pywinauto import Desktop
            desktop=Desktop(backend='uia')
        win=desktop.window(handle=chosen.hwnd)
        elements=win.descendants()[:MAX_ELEMENTS]
        if action=='inspect':
            items=[]
            for e in elements:
                role=_role(e); name=_name(e); aid=_aid(e)
                if role in INTERACTIVE and (name or aid) and not DANGEROUS.search(' '.join((name,aid))):
                    items.append({'role':role,'name':_scrub(name),'id':_scrub(aid)})
                if len(items)>=45: break
            return {'status':'observed','app':chosen.executable,'window':chosen.title[:100],
                    'controls':items,'message':'UI Automation controls inspected; no changes made.'}
        node,why=_resolve(elements,control,FILL_ROLES if action=='fill' else CLICK_ROLES)
        if node is None: return {'status':'not_ready','message':why}
        # Bind before executing: the selected window must still exist with the
        # same process, title, dimensions and HWND.
        reselected,why=_selected(target,snap)
        if reselected is None or (chosen.hwnd,chosen.executable,chosen.title,chosen.rect) != (reselected.hwnd,reselected.executable,reselected.title,reselected.rect):
            return {'status':'blocked','message':'Window identity changed; nothing was typed or clicked.'}
        if action=='fill':
            try:
                node.set_edit_text(text)
            except (AttributeError,NotImplementedError,RuntimeError,ValueError):
                node.set_focus()
                node.type_keys(text,with_spaces=True,set_foreground=True)
            try: actual=node.get_value()
            except Exception: actual=_name(node)
            checked=(actual == text)
            return {'status': 'verified' if checked else 'attempted_unverified',
                    'message': 'Text field filled and verified.' if checked else 'Text was entered but UIA could not verify the resulting value.',
                    'app':chosen.executable}
        node.click_input()
        # UI effects are not presumed; caller should re-inspect state.
        return {'status':'attempted_unverified','message':'Control clicked; re-inspect to verify the resulting app state.',
                'control':control,'app':chosen.executable}
    except Exception as exc:
        return {'status':'failed','message':'Windows UI Automation failed: '+type(exc).__name__}
