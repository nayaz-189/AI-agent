"""Conservative local Whisper transcription filter for VORAK Day 28.

Rejects empty/low-signal audio, repetition loops and output that is implausibly
long for the recorded duration. Never invents words to replace a rejection.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from .endpoint import RATE

_TOKEN = re.compile(r"\b[\w']+\b", re.UNICODE)


def _repetition_loop(words: list[str]) -> bool:
    # A repeated short sentence can evade compression-ratio checks.
    if len(words) < 12:
        return False
    for n in (4, 5, 6):
        if len(words) < n * 3:
            continue
        counts = Counter(tuple(words[i:i+n]) for i in range(len(words)-n+1))
        if counts and max(counts.values()) >= 3:
            return True
    return False


def transcript_plausible(text: str, segments, duration_s: float | None = None) -> bool:
    value = ' '.join((text or '').strip().split())
    if not value or len(value) > 1200 or not any(c.isalpha() for c in value):
        return False
    words = [m.group().casefold() for m in _TOKEN.finditer(value)]
    if not words or _repetition_loop(words):
        return False
    # Common nonspeech Whisper artifacts, distinct from arbitrary legitimate speech.
    normalized = re.sub(r'[^a-z ]', ' ', value.casefold())
    normalized = ' '.join(normalized.split())
    if normalized in {
        'thank you for watching', 'thanks for watching', 'please subscribe',
        'subscribe to my channel', 'you', 'music',
    }:
        return False
    if duration_s is not None:
        if not math.isfinite(duration_s) or duration_s < 0.32:
            return False
        # 5.3 spoken words/sec gives substantial headroom for fast natural speech.
        if len(words) > max(6, math.ceil(duration_s * 5.3)):
            return False
        if len(value) > max(50, math.ceil(duration_s * 43.0)):
            return False
    if segments:
        if all(float(getattr(s, 'no_speech_prob', 0.0) or 0.0) > 0.70 for s in segments):
            return False
        if all(float(getattr(s, 'avg_logprob', 0.0) or 0.0) < -1.15 for s in segments):
            return False
        if any(float(getattr(s, 'compression_ratio', 0.0) or 0.0) > 3.2 for s in segments):
            return False
    return True


class LocalWhisper:
    def __init__(self, model='small.en', language='en'):
        self.name = model
        self.language = language
        self.model = None

    def load(self):
        if self.model is None:
            from faster_whisper import WhisperModel
            self.model = WhisperModel(self.name, device='cpu', compute_type='int8', num_workers=2)

    def transcribe(self, pcm: bytes):
        if not pcm or len(pcm) % 2:
            return None
        import numpy as np
        audio = np.frombuffer(pcm, dtype='<i2').astype(np.float32) / 32768.0
        duration = len(audio) / RATE
        if duration < 0.40 or duration > 12.0:
            return None
        rms = float(np.sqrt(np.mean(audio * audio)))
        peak = float(np.max(np.abs(audio)))
        if not math.isfinite(rms) or rms < 0.0028 or peak < 0.018:
            return None
        # Avoid a language/topic seed causing plausible text in otherwise empty audio.
        self.load()
        result, _info = self.model.transcribe(
            audio, language='en' if self.language == 'en' else None,
            task='transcribe', beam_size=5, best_of=5,
            temperature=0, condition_on_previous_text=False,
            repetition_penalty=1.12, no_repeat_ngram_size=4,
            no_speech_threshold=0.55, log_prob_threshold=-0.85,
            compression_ratio_threshold=2.2, initial_prompt=None,
        )
        segments = list(result)
        value = ' '.join(str(s.text).strip() for s in segments).strip()
        return value if transcript_plausible(value, segments, duration) else None
