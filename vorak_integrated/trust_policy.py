"""Trusted, fail-closed target restrictions. Not an LLM preference."""
from __future__ import annotations
import re
from urllib.parse import urlsplit

# Whole-word matching: do not block innocent substrings such as 'repair'.
BLOCKED = re.compile(
    r'(?i)(?:\b(?:firefox|opera|opera gx|mozilla firefox|paytm|phonepe|gpay|google pay|paypal|razorpay|stripe|'
    r'banking|bank|wallet|upi|payment|payments|checkout|billing|credit card|debit card|password|'
    r'authenticator|credential manager|1password|bitwarden|keepass|2fa|otp|netbanking|'
    r'financial transaction|purchase|transfer money|send money|subscribe|subscription|'
    r'hdfc|icici|kotak|canara bank|axis bank|state bank|sbi|idfc|indusind|bank of baroda|'
    r'bhim|mobikwik|amazon pay|cred|slice|groww|zerodha|upstox|angel one|fi money|navi|'
    r'microsoft authenticator|google authenticator|authy|billing profile|'
    r'payment gateway|settings for payments)\b)'
)
# More restrictive for app names than ordinary website content; matches app identities.
DENIED_EXECUTABLES = {'firefox.exe','opera.exe','opera_gx.exe','launcher.exe'}
DENIED_DOMAINS = {'paypal.com','stripe.com','razorpay.com','paytm.com','phonepe.com','gpay.google.com',
                  'payments.google.com','pay.google.com','mozilla.org','firefox.com','opera.com',
                  'hdfcbank.com','icicibank.com','onlinesbi.sbi','sbi.co.in','axisbank.com',
                  'groww.in','zerodha.com','upstox.com','mobikwik.com','cred.club','kotak.com'}


def denied_name(name: str) -> bool:
    return not isinstance(name,str) or not name.strip() or bool(BLOCKED.search(name))


def denied_url(url: str) -> bool:
    try:
        p=urlsplit(url)
        host=(p.hostname or '').lower().rstrip('.')
        forbidden_path = bool(re.search(r'(?i)/(?:checkout|pay|payment|billing|password|login|signin|otp)(?:[/?#\-]|$)',p.path))
        return forbidden_path or p.scheme not in ('http','https') or not host or p.username is not None or p.password is not None or any(
            host==domain or host.endswith('.'+domain) for domain in DENIED_DOMAINS)
    except (ValueError,TypeError):
        return True


def safe_app(app: dict) -> bool:
    if not isinstance(app,dict): return False
    name=app.get('name','')
    typ=app.get('launch_type')
    target=app.get('launch_target','')
    if not isinstance(target,str) or not target.strip() or typ not in {'app_id','shortcut'}:
        return False
    if denied_name(name) or denied_name(target):return False
    # Windows packaged AppIDs can hide an executable behind generic IDs. Only
    # entries directly discovered on this machine can be used in trusted_launch.
    return True


def trusted_launch(arguments: dict, index=None) -> bool:
    """Validate exactly against Windows locally discovered identities."""
    if not isinstance(arguments,dict) or set(arguments)!={'launch_type','launch_target'}:return False
    if index is None:
        from brain.application_resolver import get_application_index
        index=get_application_index()
    for app in index.values():
        if (app.get('launch_type')==arguments['launch_type'] and
                app.get('launch_target')==arguments['launch_target']):
            return safe_app(app)
    return False


def filter_index(index: dict) -> dict:
    return {k:v for k,v in index.items() if safe_app(v)}
