"""Deterministic shortcuts for the most important explicit voice commands.
Ambiguous language is left to Gemini manual function calling, not guessed.
"""
from __future__ import annotations
import re


def quick_route(text):
    if not isinstance(text,str):return None
    q=' '.join(text.strip().split())
    if not q or len(q)>650:return None
    # Only a user command, never a how/why/hypothetical question.
    if re.match(r'(?i)^(?:how|why|what if|suppose|explain|tell me how)\b',q):return None
    m=re.fullmatch(r'(?i)(?:hey (?:v|vorak)[, ]+)?(?:please )?open\s+(.+?)[. !]*',q)
    if m and len(m.group(1))<=120 and ' and ' not in m.group(1).casefold():
        return ('open_app_or_website',{'target':m.group(1)})
    if re.fullmatch(r'(?i)(?:(?:hey (?:v|vorak)[, ]+)?(?:please )?)?(?:inspect|look at|describe|check)\s+(?:my |the )?(?:current |open )?(?:screen|desktop|display|work screen)[. !]*',q) or re.fullmatch(r'(?i)what(?:\'s| is) (?:on )?(?:my |the )?(?:current )?(?:screen|desktop|display)(?: right now)?[?. !]*',q):
        return ('inspect_screen',{'target':''})
    m=re.fullmatch(r'(?i)(?:hey (?:v|vorak)[, ]+)?(?:please )?(?:inspect|look at|describe|check)\s+(?:my |the )?(?:open |current )?(.+?)\s+(?:window|screen)[. !]*',q)
    if m and len(m.group(1))<=70:return ('inspect_screen',{'target':m.group(1)})
    # Specific, unambiguous WhatsApp-self draft request. No send capability.
    m=re.search(r'(?i)^(?:hey (?:v|vorak)[, ]+)?(?:please )?(?:open whatsapp (?:and )?)?(?:type|draft|write)\s+(?:this\s+)?(?:message\s+)?(?:to|for|in)\s+(?:myself|my own chat|message yourself)\s*[:,-]\s*(.+)$',q)
    if m and 1<=len(m.group(1))<=500:
        return ('whatsapp_self_draft',{'text':m.group(1).strip('"\' ')})
    m=re.search(r'(?i)^(?:hey (?:v|vorak)[, ]+)?(?:please )?open whatsapp and (?:type|draft|write)\s+(?:this\s+)?(?:message\s+)?(?:for|to)\s+myself\s*[:,-]\s*(.+)$',q)
    if m and 1<=len(m.group(1))<=500:
        return ('whatsapp_self_draft',{'text':m.group(1).strip('"\' ')})
    return None
