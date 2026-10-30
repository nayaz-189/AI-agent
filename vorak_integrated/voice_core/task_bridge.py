"""Bounded action bridge for VORAK's *existing* desktop and browser workers.

No arbitrary code execution, shell, coordinates, stored credentials or approvals granted by LLM output.
Only exact, named capabilities. A tool result reports an attempt, never invented success.
"""
from __future__ import annotations
import re
from urllib.parse import urlsplit

BLOCKED_TEXT = re.compile(r"(?i)\b(?:password|passcode|otp|pin|cvv|credit\s*card|debit\s*card|bank\s*account|bank\s*transfer|upi\s*pin|payment|pay\s+now|checkout|purchase|firefox|opera(?:\s+gx)?|paytm|phonepe|gpay|google\s+pay|bharatpe|razorpay|stripe|paypal|netbanking)\b")
VALID_TOOLS = frozenset({'open_app_or_website','desktop_work','browser_work','whatsapp_self_draft','inspect_screen','task_status','memory_recall'})
MAX_TEXT = 600


def _arg(args, key, limit=120):
    value=args.get(key,'')
    if not isinstance(value,str) or len(value)>limit or any(ord(c)<32 for c in value):
        raise ValueError('invalid '+key)
    return value.strip()


def _safe_output(result):
    if not isinstance(result,dict):
        return {'status':'failed','message':'Executor returned an invalid result.'}
    value={}
    for key in ('status','message','app','window','title','url','content','controls','tasks','facts'):
        item=result.get(key)
        if key in ('controls','tasks','facts') and isinstance(item,list):
            value[key]=item[:15]
        elif isinstance(item,str):
            # Preserve task information while bounding what enters the LLM.
            value[key]=item[:1000 if key=='content' else 240]
    return value if 'status' in value else {'status':'failed','message':'Missing executor status.'}


def perform(name, params, *, allow_send=False):
    """One trusted host-side action. Test dependencies are imported lazily."""
    if name not in VALID_TOOLS or not isinstance(params,dict):
        return {'status':'blocked','message':'Unknown tool.'}
    try:
        if name=='open_app_or_website':
            target=_arg(params,'target',200)
            if not target or BLOCKED_TEXT.search(target):return {'status':'blocked','message':'Protected target.'}
            from vorak_integrated.actions import open_target
            return _safe_output(open_target(target,confirm=None))
        if name=='whatsapp_self_draft':
            text=_arg(params,'text',MAX_TEXT)
            if not text or BLOCKED_TEXT.search(text):return {'status':'blocked','message':'Message contains a protected term.'}
            from vorak_integrated.whatsapp_work import self_message
            # Deliberately DRAFT ONLY in first implementation. Never send.
            return _safe_output(self_message(text,send=False))
        if name=='desktop_work':
            action=_arg(params,'action',16)
            target=_arg(params,'target',100)
            control=_arg(params,'control',120)
            text=_arg(params,'text',MAX_TEXT)
            if action not in ('inspect','fill','click') or BLOCKED_TEXT.search(target+' '+control):
                return {'status':'blocked','message':'Protected or invalid Windows task.'}
            from vorak_integrated.workspace_control import act
            return _safe_output(act(action=action,target=target,control=control,text=text))
        if name=='browser_work':
            action=_arg(params,'action',16)
            url=_arg(params,'url',2000)
            role=_arg(params,'role',24)
            control=_arg(params,'name',120)
            text=_arg(params,'text',MAX_TEXT)
            if action not in ('open','inspect','fill','click') or BLOCKED_TEXT.search(control):
                return {'status':'blocked','message':'Protected browser action.'}
            from vorak_integrated.browser_workspace import act
            return _safe_output(act(action=action,url=url,role=role,name=control,text=text))
        if name=='inspect_screen':
            target=_arg(params,'target',100)
            if BLOCKED_TEXT.search(target):return {'status':'blocked','message':'Protected window.'}
            from vorak_integrated.screen_focus import capture_work_window
            data,note=capture_work_window(target)
            if not data:return {'status':'blocked','message':note}
            # Send a one-shot vetted window image only to the configured Gemini API.
            return {'status':'image_ready','message':note,'_image':data}
        if name=='memory_recall':
            query=_arg(params,'query',120)
            if not query or BLOCKED_TEXT.search(query):return {'status':'blocked','message':'Protected memory query.'}
            from vorak_integrated.session_data import recall
            return _safe_output(recall(query))
        if name=='task_status':
            from vorak_integrated.session_data import tasks
            return _safe_output(tasks())
    except (ImportError,ModuleNotFoundError) as error:
        return {'status':'not_ready','message':'An action component is not installed: '+error.__class__.__name__}
    except Exception as error:
        return {'status':'failed','message':'Task error: '+error.__class__.__name__}
    return {'status':'blocked','message':'Not supported.'}


def public_result(result):
    return _safe_output(result)


def tool_specifications(types):
    """The model receives a finite schema, not direct Python callables."""
    specs=[
       ('open_app_or_website','Open a permitted installed Windows application or known website by name.',{'target':('string','Application or website name')},['target']),
       ('whatsapp_self_draft','TYPE a draft in verified WhatsApp Message Yourself only. Do not send.',{'text':('string','Exact message to draft')},['text']),
       ('desktop_work','Inspect, fill or click a named Windows UI Automation control in an explicitly named safe app.',{'action':('string','inspect, fill, or click'),'target':('string','Window name or empty for foreground'),'control':('string','Exact UIA control name for fill or click'),'text':('string','Value for fill')},['action']),
       ('browser_work','Operate an isolated unsigned-in Chromium browser using accessible roles.',{'action':('string','open, inspect, click, fill'),'url':('string','HTTP(S) URL for open'),'role':('string','Exact accessible role'),'name':('string','Exact accessible control name'),'text':('string','Text to fill')},['action']),
       ('inspect_screen','Read the currently focused permitted Windows app, or one named app, via one screenshot.',{'target':('string','Optional window name. Empty for foreground.')},[]),
       ('memory_recall','Look up available explicit user memory facts.',{'query':('string','A search phrase')},['query']),
       ('task_status','Get recent task outcomes, not a promise of completion.',{},[])
    ]
    functions=[]
    for name,description,fields,required in specs:
        parameters={'type':'object','properties':{key:{'type':typ,'description':desc} for key,(typ,desc) in fields.items()}}
        if required:parameters['required']=required
        functions.append(types.FunctionDeclaration(name=name,description=description,parameters_json_schema=parameters))
    return [types.Tool(function_declarations=functions)]
