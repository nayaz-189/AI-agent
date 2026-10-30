"""Isolated, explicit development modes; never treat unauthenticated speech as owner authority.

Modes:
 - stt: microphone -> local Whisper -> print transcription (no Gemini or actions).
 - chat: microphone -> local Whisper -> Gemini text (NO TOOLS) -> direct Gemini TTS.
 - terminal: typed commands -> existing authenticated-Windows-session local Gemini tool bridge.

Do not use chat mode for granting access to apps; it intentionally has no tools.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
from .config import Settings, VOICES


def load_keys():
    try:
        from dotenv import load_dotenv
    except ImportError:return
    repo=Path(__file__).resolve().parents[2]
    for path in (repo/'.env', repo/'vorak_gemini'/'.env'):
        if path.is_file(): load_dotenv(path, override=False)


class GeminiTextOnly:
    """NO tool declarations; NO executor; NO desktop access, by design."""
    def __init__(self, client=None, model=None):
        load_keys()
        if client is None:
            from google import genai
            client=genai.Client()
        self.client=client
        self.model=model or os.getenv('VORAK_TEXT_MODEL','gemini-3.8-flash')
        self.history=[]

    def ask(self, question):
        from google.genai import types
        if not isinstance(question,str) or not question.strip(): raise ValueError('Empty question')
        user=types.Content(role='user',parts=[types.Part.from_text(text=question.strip())])
        response=self.client.models.generate_content(
            model=self.model,contents=[*self.history[-20:],user],
            config=types.GenerateContentConfig(
                system_instruction='You are VORAK. Keep a natural casual voice, with occasional banter; be precise for serious topics. Never claim access to applications or the internet unless you actually have it. One clear answer.',
                temperature=0.5,max_output_tokens=400))
        answer=(getattr(response,'text',None) or '').strip()
        if not answer:raise RuntimeError('Gemini returned an empty answer')
        self.history=(self.history+[user,types.Content(role='model',parts=[types.Part.from_text(text=answer)])])[-20:]
        return answer


def build_stt(model, language):
    from .transcriber import LocalWhisper
    stt=LocalWhisper(model,language)
    print('Loading local transcription model:',model,flush=True)
    stt.load()
    return stt


def run_microphone(mode,args):
    from .endpoint import Microphone
    stt=build_stt(args.stt_model,args.stt_language)
    if mode=='chat':
        gemini=GeminiTextOnly()
        # TTS is reused from the known voice-core implementation. Its ask()
        # method is NEVER called from this mode, so no model tools are exposed.
        from .gemini_voice import GeminiVoice
        tts=GeminiVoice()
        from .playback import speak
    print('MODE:',mode.upper(),'| NOT OWNER VERIFIED | NO APP ACTIONS',flush=True)
    print('No audio is saved by this laboratory. Ctrl+C ends it.',flush=True)
    with Microphone(args.mic_device) as mic:
        while True:
            pcm=mic.collect(silence_ms=1250,min_speech_ms=300,max_seconds=11)
            if not pcm:continue
            text=stt.transcribe(pcm)
            if not text:continue
            print('YOU:',text,flush=True)
            if mode=='chat':
                try:
                    answer=gemini.ask(text)
                    print('VORAK:',answer,flush=True)
                    wav=tts.speech(answer,args.profile)
                    speak(wav,mic,allow_barge_in=False,speaker_device=None)
                except KeyboardInterrupt:raise
                except Exception as exc:
                    print('LAB ERROR:',type(exc).__name__,str(exc)[:150],flush=True)
                    mic.flush()


def run_terminal(args):
    """Local keyboard session for action-testing; this is NOT voice authentication."""
    from .gemini_voice import GeminiVoice
    gemini=GeminiVoice()
    print('TYPED TASK LAB: permission = access to this local Windows terminal, not recognized voice identity.')
    print('Existing protected-app restrictions remain; WhatsApp drafts only, no Send. Type /quit to stop.')
    while True:
        try:line=input('YOU (keyboard): ').strip()
        except EOFError:break
        if line in {'/quit','/exit'}:break
        if not line:continue
        answer=gemini.ask(line)
        print('VORAK:',answer,flush=True)


def main(argv=None):
    p=argparse.ArgumentParser(description='Isolated VORAK microphone/STT/Gemini diagnostics and keyboard task test')
    p.add_argument('mode',choices=('stt','chat','terminal'))
    p.add_argument('--mic-device',type=int,default=1)
    p.add_argument('--stt-model',default='tiny.en')
    p.add_argument('--stt-language',choices=('en','auto'),default='en')
    p.add_argument('--profile',choices=sorted(VOICES),default='alex')
    a=p.parse_args(argv)
    if a.stt_language=='auto' and a.stt_model.endswith('.en'):p.error('Multilingual model required for auto language')
    try:
        if a.mode=='terminal':run_terminal(a)
        else:run_microphone(a.mode,a)
    except KeyboardInterrupt:
        print('\nStopped.')
        return 0
    return 0

if __name__=='__main__':main()
