"""Voice configuration only; no global side effects or stored credentials."""
from dataclasses import dataclass
import os

VOICES = {'alex': 'Puck', 'raju': 'Fenrir', 'ankita': 'Kore', 'leah': 'Aoede'}

@dataclass(frozen=True)
class Settings:
    mic_device: int | None = 1
    speaker_device: int | None = None
    profile: str = 'alex'
    model: str = os.getenv('VORAK_TEXT_MODEL', 'gemini-3.8-flash')
    tts_model: str = os.getenv('VORAK_TTS_MODEL', 'gemini-3.8-flash-tts')
    stt_model: str = os.getenv('VORAK_STT_MODEL', 'small.en')
    language: str = os.getenv('VORAK_STT_LANGUAGE', 'en')
    silence_ms: int = 1250
    min_speech_ms: int = 220
    max_utterance_s: float = 11.0
    audio_mode: str = 'speakers'
    require_owner: bool = True
    max_turns: int = 12

    def __post_init__(self):
        if self.profile not in VOICES: raise ValueError('Unknown voice profile')
        if self.audio_mode not in ('speakers','headset'): raise ValueError('Unknown audio mode')
        if self.language not in ('en','auto'): raise ValueError('Unsupported language mode')
        if not (500 <= self.silence_ms <= 2500): raise ValueError('Invalid silence threshold')
        if not (0.2 <= self.max_utterance_s <= 11.5): raise ValueError('Invalid duration')

# Minimal instructions: no inherited tool declarations, elaborate personas, or action commands.
BASE_INSTRUCTION = ('You are VORAK, a helpful conversational assistant. Answer the user clearly and accurately. '
                    'Use natural friendly language, a little occasional humor when appropriate, and a serious tone for serious topics. '
                    'Respond in one coherent paragraph unless the user explicitly asks for another format. '
                    'Do not claim to have used a tool or accessed the computer. Do not fabricate facts.')
