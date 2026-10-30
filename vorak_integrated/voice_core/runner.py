"""Single clean runtime, no imported old voice commands or Gemini Live instructions."""
import argparse
import time
from .config import Settings,VOICES
from .endpoint import Microphone
from .transcriber import LocalWhisper
from .gemini_voice import GeminiVoice
from .identity import ExistingOwnerGate, OwnerUnavailable, condition_pcm
from .playback import speak


def joined_question(previous,followup):
    """Carry context for a genuine interruption; don't concatenate hallucinated fragments."""
    a=' '.join((previous or '').split()); b=' '.join((followup or '').split())
    if not a:return b
    if not b:return a
    if b.casefold() in {'wait','hold on','one second','stop'}:return a
    return a+'\nClarification or follow-up: '+b


def checked_audio(pcm, gate):
    """Reject audio without creating a transcript; keep the enrolled ECAPA threshold."""
    check = gate.check(pcm) if gate else condition_pcm(pcm)
    if gate and not check.accepted:
        print('OWNER CHECK:', check.status, f'duration={check.seconds:.2f}s',
              f'mic_rms={check.input_rms:.5f}', flush=True)
        # A short Windows notification for an actual full-length rejected sample.
        # No Gemini request and no private details are spoken to an unknown speaker.
        if check.seconds >= 2 and check.status in {'speaker_mismatch', 'verification_uncertain'}:
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except (ImportError, OSError):
                pass
        return None
    if not gate and check.conditioned_pcm is None:
        print('AUDIO CHECK:', check.status, flush=True)
        return None
    return check.conditioned_pcm


def diagnose_owner(settings):
    """Local only: never invoke Gemini, Whisper or an app; never save recordings."""
    gate = ExistingOwnerGate()
    print('Owner microphone test (no audio saved or transmitted).',flush=True)
    print('Speak a clear, new sentence lasting at least three seconds, then pause.',flush=True)
    with Microphone(settings.mic_device) as mic:
        pcm = mic.collect(silence_ms=settings.silence_ms,
                          min_speech_ms=settings.min_speech_ms,
                          max_seconds=settings.max_utterance_s)
    if not pcm:
        print('No speech segment captured. Confirm the selected microphone and Windows input gain.')
        return 2
    result = gate.check(pcm)
    print('Owner test:', result.status, f'duration={result.seconds:.2f}s',
          f'mic_rms={result.input_rms:.5f}')
    if result.status == 'verification_uncertain':
        print('Verifier returned UNCERTAIN. Run python -m voice.cli verify for the independent original verifier diagnostic.')
    if result.status == 'speaker_mismatch':
        print('Model evaluated the audio but did not match the existing calibrated owner threshold.')
    if result.status == 'too_short_for_owner_check':
        print('Existing ECAPA verification requires at least 2 seconds of speech.')
    return 0 if result.accepted else 2


def run(settings:Settings):
    if settings.require_owner:
        # Never open the microphone until identity gate prerequisites exist.
        gate=ExistingOwnerGate()
    else:gate=None
    stt=LocalWhisper(settings.stt_model,settings.language)
    print('Loading local speech model; the first run may download weights.',flush=True)
    try:
        import psutil
        free=psutil.virtual_memory().available//(1024*1024)
        if free<1800 and settings.stt_model in ('small.en','small'):
            print(f'LOW MEMORY: {free} MB free; small.en may stall or exhaust RAM. For a lighter first test pass --stt-model tiny.en.',flush=True)
    except ImportError:pass
    stt.load()
    gemini=GeminiVoice(settings.model,settings.tts_model)
    print('VORAK voice + task bridge ready. Voice: '+settings.profile+'. Ctrl+C stops.',flush=True)
    print(('Owner-only verification active.' if gate else 'WARNING: owner verification disabled for development.'),flush=True)
    pending=None
    pending_since=0.0
    ready_text=None
    with Microphone(settings.mic_device) as microphone:
        while True:
            if ready_text is not None:
                question=ready_text; ready_text=None
            else:
                pcm=microphone.collect(silence_ms=settings.silence_ms,
                                  min_speech_ms=settings.min_speech_ms,
                                  max_seconds=settings.max_utterance_s)
                if pcm is None:continue
                accepted = checked_audio(pcm, gate)
                if accepted is None: continue
                question=stt.transcribe(accepted)
                if not question:continue
            if pending:
                if time.monotonic() - pending_since < 25:
                    question=joined_question(pending,question)
                pending=None
            print('YOU:',question,flush=True)
            try:
                reply=gemini.ask(question,settings.max_turns)
                print('VORAK:',reply,flush=True)
                wav=gemini.speech(reply,settings.profile)
                # Built-in speakers produce echoes. Voice barge-in requires headset mode.
                interruption=speak(wav,microphone,allow_barge_in=settings.audio_mode=='headset',
                                   silence_ms=settings.silence_ms,speaker_device=settings.speaker_device)
                if interruption:
                    # A short spoken stop may halt playback but cannot authenticate a task.
                    # Preserve context and wait for the next independently verified sentence.
                    approved = checked_audio(interruption, gate)
                    if approved is None:
                        pending=question; pending_since=time.monotonic()
                        print('VORAK: Stopped. I am listening for your full question.',flush=True)
                        microphone.flush()
                        continue
                    followup=stt.transcribe(approved)
                    if followup:
                        print('YOU (interrupt):',followup,flush=True)
                        if followup.casefold().strip(' .!,') in {'wait','hold on','one second','stop'}:
                            pending=question; pending_since=time.monotonic()
                        else:
                            ready_text=joined_question(question,followup)
            except KeyboardInterrupt: raise
            except Exception as err:
                print('VOICE ERROR:',type(err).__name__,str(err)[:180],flush=True)
                microphone.flush()

def main(argv=None):
    p=argparse.ArgumentParser(description='VORAK clean local STT + Gemini text + Gemini TTS')
    p.add_argument('--profile',choices=sorted(VOICES),default='alex')
    p.add_argument('--mic-device',type=int,default=1)
    p.add_argument('--speaker-device',type=int)  # accepted for compatibility, output is default OS device
    p.add_argument('--audio-mode',choices=('speakers','headset'),default='speakers')
    p.add_argument('--stt-model',default='small.en')
    p.add_argument('--stt-language',choices=('en','auto'),default='en')
    p.add_argument('--demo-no-owner-check',action='store_true')
    p.add_argument('--owner-diagnostic',action='store_true',help='Local microphone and speaker-verification test; no Gemini requests')
    args=p.parse_args(argv)
    if args.stt_language=='auto' and args.stt_model.endswith('.en'):
        p.error('For auto languages select multilingual --stt-model small or medium')
    settings=Settings(mic_device=args.mic_device,speaker_device=args.speaker_device,
                     profile=args.profile,stt_model=args.stt_model,
                     language=args.stt_language,audio_mode=args.audio_mode,
                     require_owner=not args.demo_no_owner_check)
    try:
        if args.owner_diagnostic: return diagnose_owner(settings)
        run(settings)
    except OwnerUnavailable as e:
        print('OWNER CHECK NOT READY:',e)
        print('Set up original voice identity with: python -m voice.cli enroll / calibrate')
        print('For an unsafe, development-only STT test: add --demo-no-owner-check')
        return 2
    except KeyboardInterrupt:
        print('\nStopped.'); return 0
    return 0
