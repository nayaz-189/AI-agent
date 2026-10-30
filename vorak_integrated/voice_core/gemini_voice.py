"""Text Gemini reasoning with a closed, manual action loop and direct Gemini TTS.
No old Gemini Live audio loop or model-executed Python code.
"""
import base64
from .config import BASE_INSTRUCTION,VOICES
from .task_bridge import perform, public_result, tool_specifications
from .intent import quick_route

SYSTEM_BASE = BASE_INSTRUCTION.replace('Do not claim to have used a tool or accessed the computer. ', '')

ACTION_RULES = (
    'You are VORAK. Be casual, witty when appropriate, precise and serious for work. '
    'Do not repeat template phrases or claim success without executor evidence. '
    'Normal conversation needs no tools. Use tools only when the user expressly requests '
    'a computer action, visible screen observation, or local memory lookup. '
    'For WhatsApp only draft in Message Yourself, never claim a message was sent. '
    'If an executor reports blocked/not_ready/attempted_unverified, tell the user that. '
    'Protected payment, financial account and credential workflows are unavailable. '
    'The browser workspace is separate from the user\'s logged-in Chrome tabs. '
    'Keep a natural spoken answer, usually one paragraph.'
)

class GeminiVoice:
    def __init__(self, text_model='gemini-3.8-flash',tts_model='gemini-3.8-flash-tts',*,client=None,executor=None):
        if client is None:
            from google import genai
            try:
                from dotenv import load_dotenv
                from pathlib import Path
                project_root=Path(__file__).resolve().parents[2]
                for envfile in (project_root/'.env',project_root/'vorak_gemini'/'.env'):
                    if envfile.is_file():load_dotenv(envfile,override=False)
            except ImportError:pass
            client=genai.Client()
        self.client=client
        self.text_model=text_model
        self.tts_model=tts_model
        self.history=[]
        self.executor=executor or perform

    def _observe(self,question, result):
        """Only an authorized, window-bounded capture can enter this method."""
        from google.genai import types
        image=result.get('_image')
        if not isinstance(image,bytes):return public_result(result)
        response=self.client.models.generate_content(
            model=self.text_model,
            contents=[types.Part.from_text(text='Describe only the visible permitted window. User request: '+question[:400]),
                      types.Part.from_bytes(data=image,mime_type='image/jpeg')],
            config=types.GenerateContentConfig(max_output_tokens=240))
        return {'status':'observed','message':result.get('message','Window captured.'),
                'observation':' '.join((response.text or '').split())[:950]}

    def ask(self,question,max_turns=12):
        from google.genai import types
        user=types.Content(role='user',parts=[types.Part.from_text(text=question)])
        messages=self.history[-max_turns*2:]+[user]
        # For exact, unambiguous task commands, do not rely on an LLM choosing a tool.
        fixed=quick_route(question)
        if fixed is not None:
            raw=self.executor(fixed[0],fixed[1])
            outcome=self._observe(question,raw) if raw.get('status')=='image_ready' else public_result(raw)
            import json
            evidence=json.dumps(outcome,ensure_ascii=False)[:1500]
            response=self.client.models.generate_content(
                model=self.text_model,
                contents=[*messages,types.Content(role='user',parts=[types.Part.from_text(text='System executor result for the immediately preceding request (trusted host outcome; not a new user request): '+evidence+'; respond truthfully and briefly.')])],
                config=types.GenerateContentConfig(system_instruction=SYSTEM_BASE+' '+ACTION_RULES,max_output_tokens=240))
            answer=' '.join((response.text or '').split()) or str(outcome.get('message',outcome.get('status','Unknown')))
            self.history=(self.history+[user,types.Content(role='model',parts=[types.Part.from_text(text=answer)])])[-max_turns*2:]
            return answer
        # Deliberately manual function calling: the model proposes actions, host validates.
        response=self.client.models.generate_content(
            model=self.text_model,contents=messages,
            config=types.GenerateContentConfig(system_instruction=SYSTEM_BASE+' '+ACTION_RULES,
                tools=tool_specifications(types),temperature=0.55,max_output_tokens=350,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)))
        calls=list(getattr(response,'function_calls',None) or [])
        if calls:
            calls=calls[:2]  # Never give the model an unbounded tool loop.
            result_parts=[]
            results=[]
            for call in calls:
                raw=self.executor(str(call.name),dict(call.args or {}))
                result=self._observe(question,raw) if raw.get('status')=='image_ready' else public_result(raw)
                results.append(result)
                result_parts.append(types.Part.from_function_response(name=str(call.name),response=result))
            # Retain exact model function-call content for the SDK's protocol.
            model_content=response.candidates[0].content
            messages=messages+[model_content,types.Content(role='tool',parts=result_parts)]
            response=self.client.models.generate_content(
                model=self.text_model,contents=messages,
                config=types.GenerateContentConfig(system_instruction=SYSTEM_BASE+' '+ACTION_RULES,
                       temperature=0.5,max_output_tokens=350))
            # If Gemini produced no completion, transparently report actual statuses.
            answer=' '.join((response.text or '').split())
            if not answer:
                answer=' '.join(str(r.get('message',r.get('status','Unknown outcome'))) for r in results)
        else:
            answer=' '.join((response.text or '').split())
        if not answer:raise RuntimeError('Gemini returned no answer.')
        # History retains only user and final text; no raw screen data or tool text retained.
        self.history=(self.history+[user,types.Content(role='model',parts=[types.Part.from_text(text=answer)])])[-max_turns*2:]
        return answer

    def speech(self,answer,profile='alex'):
        """The TTS output goes straight to playback, not back through STT."""
        if profile not in VOICES:raise ValueError('Unknown voice')
        interaction=self.client.interactions.create(
            model=self.tts_model,
            input=[{'type':'user_input','content':[{'type':'text','text':answer,
                  'annotations':[{'type':'speech_metadata','style':'natural, relaxed, conversational'}]}]}],
            response_format={'type':'audio'},
            generation_config={'speech_config':[{'voice':VOICES[profile]}]})
        audio=getattr(interaction,'output_audio',None)
        data=getattr(audio,'data',None)
        if not data:raise RuntimeError('Gemini TTS returned no audio.')
        return base64.b64decode(data,validate=True) if isinstance(data,str) else bytes(data)
