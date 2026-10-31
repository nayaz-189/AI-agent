"""Trusted application and web action dispatcher, kept separate from the model.
Only registered app identities can be launched; exact requests use existing policy gate.
"""
from __future__ import annotations
import html
import re
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from html.parser import HTMLParser

_RECENT_APP_DISPATCH = {}
_RECENT_APP_LOCK = threading.Lock()
_RECENT_URL_OPEN = {}
_RECENT_URL_LOCK = threading.Lock()
_APP_DISPATCH_COOLDOWN = 20.0  # avoid repeated launches during one voice task

KNOWN = {'google':'https://www.google.com','youtube':'https://www.youtube.com',
         'github':'https://github.com','gmail':'https://mail.google.com',
         'whatsapp web':'https://web.whatsapp.com','chatgpt':'https://chatgpt.com'}

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.items=[]; self.active=None; self.words=[]
    def handle_starttag(self, tag, attrs):
        if tag != 'a': return
        attrs = dict(attrs); url = attrs.get('href','')
        if 'result__a' in attrs.get('class','') and url:
            self.active=url; self.words=[]
    def handle_data(self, data):
        if self.active: self.words.append(data)
    def handle_endtag(self, tag):
        if tag=='a' and self.active:
            self.items.append((' '.join(self.words).strip(),self.active)); self.active=None

def clean_link(url):
    if url.startswith('//'): url='https:'+url
    p=urllib.parse.urlsplit(url)
    if p.path.startswith('/l/') and p.netloc.endswith('duckduckgo.com'):
        url=urllib.parse.parse_qs(p.query).get('uddg',[''])[0]
        p=urllib.parse.urlsplit(url)
    if p.scheme not in ('https','http') or not p.hostname or p.username or p.password:
        return None
    if p.hostname.endswith('duckduckgo.com'): return None
    from vorak_integrated.trust_policy import denied_url
    if denied_url(url):return None
    return url

def web_candidates(query, fetch=None):
    query=query.strip()[:120]
    if not query: return []
    if query.lower() in KNOWN:
        from vorak_integrated.trust_policy import denied_url
        if denied_url(KNOWN[query.lower()]):return []
        return [(query.title(),KNOWN[query.lower()])]
    direct=clean_link(query if '://' in query else 'https://'+query)
    if ('.' in query and ' ' not in query and direct):
        return [(query,direct)]
    url='https://html.duckduckgo.com/html/?'+urllib.parse.urlencode({'q':query})
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; VORAK/1.0)'})
        raw=(fetch(req,timeout=2.3) if fetch else urllib.request.urlopen(req,timeout=2.3)).read(250000)
        parser=Links();parser.feed(raw.decode('utf-8','replace'))
        output=[]; seen=set()
        for title,link in parser.items:
            link=clean_link(html.unescape(link))
            if not link: continue
            host=urllib.parse.urlsplit(link).hostname
            if host not in seen:
                seen.add(host);output.append((html.unescape(title)[:85] or host,link))
            if len(output)>=3: break
        return output
    except (OSError,ValueError,TimeoutError): return []

def choose_sites(items, query, select=None):
    """One Tk interface with up to three candidate websites. No auto-pick on ambiguity."""
    if select: return select(items)
    import tkinter as tk
    root=tk.Tk(); root.title('VORAK — Website matches'); root.geometry('670x290')
    root.attributes('-topmost',True)
    result={'url':None}
    tk.Label(root,text='Choose a website for: '+query[:75],font=('Segoe UI',12,'bold')).pack(pady=12)
    for title,url in items[:3]:
        def click(u=url): result['url']=u;root.destroy()
        tk.Button(root,text=title+'  —  '+urllib.parse.urlsplit(url).hostname,command=click,wraplength=600,width=85).pack(pady=5)
    tk.Button(root,text='Cancel',command=root.destroy).pack(pady=10)
    root.protocol('WM_DELETE_WINDOW',root.destroy)
    root.mainloop();return result['url']

_RESOLVER_CACHE = {}

def launch_app(name, confirm=None, resolver=None, gate_factory=None):  # VORAK_AUTOMATION_BRIDGE_V12
    """No fallback for an ambiguous app; app path and target never come from the model."""
    if not isinstance(name,str) or not (1<=len(name.strip())<=100):
        return {'status':'invalid','message':'Invalid application name.'}
    if resolver is None:
        from brain.application_resolver import find_application
        resolver=find_application
    # Cache only stable application resolution, never approvals or launch results.
    # First lookup still enumerates apps and can take longer.
    from_default = getattr(resolver,'__module__','') == 'brain.application_resolver'
    key=name.strip().casefold()
    candidate=_RESOLVER_CACHE.get(key) if from_default else None
    if candidate is None:
        candidate=resolver(name)
        if from_default and isinstance(candidate,dict) and candidate.get('status')=='resolved':
            if len(_RESOLVER_CACHE) >= 64: _RESOLVER_CACHE.clear()
            _RESOLVER_CACHE[key]=candidate
    if not candidate: return {'status':'not_found','message':'No installed application matched.'}
    if candidate.get('status')!='resolved':
        return {'status':'ambiguous','message':'More than one installed application matched.'}
    app=candidate['application']
    request={'action':'launch_application','arguments':{'launch_type':app['launch_type'],'launch_target':app['launch_target']}}
    from desktop.consequence_policy import ConsequencePolicy,PolicyDecision
    decision=ConsequencePolicy().evaluate(request).decision
    if decision==PolicyDecision.DENY or decision==PolicyDecision.UNKNOWN:
        return {'status':'blocked','message':'Launch denied by desktop policy.'}
    if gate_factory is None:
        from desktop.desktop_execution_gate import DesktopExecutionGate
        gate_factory=DesktopExecutionGate
    gate=gate_factory();token=None
    if decision==PolicyDecision.CONFIRM:
        if confirm is None or not confirm('Launch '+app['name']+'?'):
            return {'status':'cancelled','message':'Launch cancelled by owner.'}
        token=gate.confirmation_authority.issue(request).token
    # Repeated Live function calls must not reopen the same application.
    # Reserve before dispatch so concurrent calls cannot launch duplicates.
    launch_key=(app['launch_type'],app['launch_target'])
    with _RECENT_APP_LOCK:
        now=time.monotonic()
        if now - _RECENT_APP_DISPATCH.get(launch_key,-1e12) < _APP_DISPATCH_COOLDOWN:
            return {'status':'already_requested',
                    'message':'Application launch was already dispatched recently. Reuse or inspect the existing window; do not reopen it.'}
        _RECENT_APP_DISPATCH[launch_key]=now
    try:
        outcome=gate.execute(request,confirmation_token=token)
    except Exception:
        with _RECENT_APP_LOCK:
            _RECENT_APP_DISPATCH.pop(launch_key,None)
        raise
    if not outcome.get('success'):
        with _RECENT_APP_LOCK:
            _RECENT_APP_DISPATCH.pop(launch_key,None)
        return {'status':'failed','message':str(outcome.get('error') or 'Launch failed.')}
    is_web_app = str(app.get('launch_target','')).casefold().startswith('chrome._crx_')
    kind='Chrome-installed web app shortcut' if is_web_app else 'installed application'
    return {'status':'dispatched','message':kind+' launch dispatched for '+app['name']+'. Window visibility not yet verified.'}

def open_target(name, confirm=None, resolver=None, choose=None, search=None, browser=None, gate_factory=None):
    """Exact app lookup first, then website lookup. Network time is not guaranteed."""
    started=time.perf_counter()
    # Independent defense: tools and model prompt cannot bypass this boundary.
    from vorak_integrated.trust_policy import denied_name
    if denied_name(name):
        return {'status':'blocked','message':'Payment/credential action or invalid target denied.'}
    # Direct URLs and configured known sites should never scan 166 apps.
    direct_site = name.strip().casefold() in KNOWN or (not any(c.isspace() for c in name.strip())
                    and (name.startswith(('https://','http://')) or
                         ('.' in name and not name.casefold().endswith('.exe'))))
    if direct_site:
        items=(search or web_candidates)(name)
    else:
        app=launch_app(name,confirm=confirm,resolver=resolver,gate_factory=gate_factory)
        if app['status']!='not_found':
            app['elapsed_ms']=round((time.perf_counter()-started)*1000); return app
        items=(search or web_candidates)(name)
    if not items:
        return {'status':'not_found','message':'I could not confidently identify a website. What website did you mean?'}
    if len(items)>1 and choose is None:
        return {'status':'ambiguous','message':'Which website would you like to open?',
                'candidates':[{'title':title[:80],'url':url[:250]} for title,url in items[:3]]}
    link=items[0][1] if len(items)==1 else choose_sites(items,name,select=choose)
    if not link:return {'status':'cancelled','message':'Website selection cancelled.'}
    opener=browser or chrome_open
    if browser is None:
        # Chrome tab opening must be idempotent across repeat voice tool calls.
        with _RECENT_URL_LOCK:
            now=time.monotonic()
            if now - _RECENT_URL_OPEN.get(link, -1e12) < _APP_DISPATCH_COOLDOWN:
                return {'status':'already_requested','url':link,
                        'message':'This website was opened recently. Reuse the existing tab, do not open another.'}
            worked=opener(link)
            if worked:
                _RECENT_URL_OPEN[link]=now
                if len(_RECENT_URL_OPEN)>100:
                    _RECENT_URL_OPEN.clear()
                    _RECENT_URL_OPEN[link]=now
    else:
        worked=opener(link)
    return {'status':'opened' if worked else 'failed','url':link,
            'message':'Opened '+link if worked else 'Browser reported launch failure.',
            'elapsed_ms':round((time.perf_counter()-started)*1000)}



def chrome_open(url):
    """Launch explicit Chrome, never invoke a banned default Firefox/Opera browser."""
    from vorak_integrated.trust_policy import denied_url
    if denied_url(url):return False
    import os
    import shutil
    import subprocess
    from pathlib import Path
    candidates = [
        shutil.which('chrome'),
        str(Path(os.environ.get('PROGRAMFILES',r'C:\Program Files'))/'Google'/'Chrome'/'Application'/'chrome.exe'),
        str(Path(os.environ.get('PROGRAMFILES(X86)',r'C:\Program Files (x86)'))/'Google'/'Chrome'/'Application'/'chrome.exe'),
        str(Path(os.environ.get('LOCALAPPDATA',''))/'Google'/'Chrome'/'Application'/'chrome.exe'),
    ]
    for exe in candidates:
        if exe and Path(exe).is_file():
            try:
                subprocess.Popen([exe,url],shell=False,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                return True
            except OSError:
                continue
    return False
