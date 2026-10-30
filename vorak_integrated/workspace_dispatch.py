"""Narrow, auditable dispatch boundary for the Gemini Live function tools."""
from __future__ import annotations
from vorak_integrated.session_data import task,remember,recall,tasks,legacy_project_memory


def dispatch(kind, options=None):
    p=options if isinstance(options,dict) else {}
    if kind=='desktop_work':
        from vorak_integrated.workspace_control import act
        answer=act(action=str(p.get('action','inspect')),target=str(p.get('target','')),
                   control=str(p.get('control','')),text=str(p.get('text','')))
    elif kind=='browser_work':
        from vorak_integrated.browser_workspace import act
        answer=act(action=str(p.get('action','inspect')),url=str(p.get('url','')),
                   role=str(p.get('role','')),name=str(p.get('name','')),text=str(p.get('text','')))
    elif kind=='whatsapp_self_work':
        from vorak_integrated.whatsapp_work import self_message
        answer=self_message(str(p.get('text','')),send=p.get('send',False) is True)
    elif kind=='memory_recall':answer=recall(str(p.get('query','')))
    elif kind=='memory_remember':answer=remember(str(p.get('key','')),str(p.get('value','')))
    elif kind=='legacy_project_memory':answer=legacy_project_memory()
    elif kind=='task_status':answer=tasks()
    else:answer={'status':'blocked','message':'Unregistered workspace tool.'}
    return task(kind,answer)
