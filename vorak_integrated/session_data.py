"""Local task journal and explicitly requested memory, no agent or paid-provider activation."""
from __future__ import annotations
from contextlib import contextmanager
import json
from pathlib import Path
import re
import sqlite3
import threading
import time

LOCK=threading.RLock()
SECRET=re.compile(r'(?i)\b(?:password|passcode|pin|otp|token|api.key|secret|credit.card|debit.card|cvv|bank.account)\b')


def _path():
    return Path(__file__).resolve().parents[1]/'runtime'/'vorak'/'state.sqlite3'


def _db():
    file=_path();file.parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(str(file),timeout=5)
    con.execute('CREATE TABLE IF NOT EXISTS memories (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated REAL NOT NULL)')
    con.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, status TEXT NOT NULL, info TEXT, updated REAL NOT NULL)')
    return con


@contextmanager
def _connection():
    with LOCK:
        connection=_db()
        try:
            with connection: yield connection
        finally: connection.close()


def remember(key,value):
    if not isinstance(key,str) or not isinstance(value,str) or not (1<=len(key)<=70 and 1<=len(value)<=500):
        return {'status':'blocked','message':'Invalid memory length.'}
    if SECRET.search(key) or SECRET.search(value):return {'status':'blocked','message':'Never store credentials in memory.'}
    clean=' '.join(key.strip().lower().split())
    with _connection() as con:
        con.execute('INSERT OR REPLACE INTO memories(key,value,updated) VALUES (?,?,?)',(clean,value.strip(),time.time()))
    return {'status':'saved','message':'Saved that fact in VORAK local memory.'}


def recall(query):
    if not isinstance(query,str) or len(query)>150:return {'status':'blocked','message':'Invalid memory request.'}
    q=' '.join(query.lower().split())
    if SECRET.search(q):return {'status':'blocked','message':'Sensitive memory lookup denied.'}
    with _connection() as con:
        rows=con.execute('SELECT key,value FROM memories ORDER BY updated DESC LIMIT 80').fetchall()
    hits=[{'key':k,'value':v} for k,v in rows if q in k or q in v.lower() or any(term in k for term in q.split() if len(term)>3)]
    if not hits and q in {'all','everything','who am i','my profile','my name','name'}:
        hits=[{'key':k,'value':v} for k,v in rows[:10]]
    return {'status':'found' if hits else 'not_found','facts':hits[:8]}


def identity_context():
    """Only explicit non-secret personal memory enters the next Live session."""
    try:
        with _connection() as con:
            facts=con.execute('SELECT key,value FROM memories ORDER BY updated DESC LIMIT 8').fetchall()
        if not facts:return ''
        items=[k+': '+v for k,v in facts if not SECRET.search(k+' '+v)]
        return '\nVerified local VORAK memory (do not invent missing facts): '+json.dumps(items,ensure_ascii=False)[:1200]+'\n'
    except Exception:return ''


def task(name,output):
    """Best-effort audit journal. Never persist messages, page contents, or credentials."""
    if not isinstance(output,dict):return output
    status=str(output.get('status','unknown'))[:50]
    label=str(name)[:70]
    try:
        with _connection() as con:
            con.execute('INSERT INTO tasks(name,status,info,updated) VALUES (?,?,?,?)',(label,status,'',time.time()))
    except Exception:pass
    return output


def tasks(limit=10):
    limit=max(1,min(int(limit),20))
    try:
        with _connection() as con:
            rows=con.execute('SELECT id,name,status,updated FROM tasks ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
        return {'status':'ok','tasks':[{'id':i,'task':n,'status':s} for i,n,s,t in rows]}
    except Exception:return {'status':'unavailable','tasks':[]}


def legacy_project_memory():
    """Bridge existing local repository knowledge read-only, with bounded output.
    It is project history, not proof of the user's personal identity.
    """
    try:
        from knowledge.canonical_query import get_knowledge_summary, get_recent_events
        summary=get_knowledge_summary()
        # Never return full event payload, because legacy events can contain secrets.
        recent=get_recent_events(limit=5)
        labels=[]
        for entry in (recent or []):
            if isinstance(entry,dict):
                labels.append(str(entry.get('event_type',entry.get('type','event')))[:50])
        return {'status':'ok','project_summary':str(summary)[:500],'recent_event_types':labels}
    except Exception as exc:
        return {'status':'unavailable','message':'Legacy project memory unavailable: '+type(exc).__name__}
