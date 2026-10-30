"""Lightweight microphone gating and transcript feedback suppression for VORAK.

No recordings are stored. One AudioGuard instance is scoped to one Live session.
This is NOT acoustic echo cancellation: headphones remain the reliable full-duplex mode.
The gate emits PCM16 silence for low-confidence audio, retaining audio pre-roll so
speech onsets are not lost. Never use the transcript filter for security decisions.
"""
from __future__ import annotations

from collections import deque
from difflib import SequenceMatcher
from time import monotonic
import math
import re
import threading

import numpy as np


def rms_peak(pcm: bytes) -> tuple[float, float]:
    """Get normalized RMS/peak of mono 16-bit LE audio. Fail closed for bad data."""
    if not isinstance(pcm, bytes) or len(pcm) < 160 or len(pcm) % 2:
        return 0.0, 0.0
    audio = np.frombuffer(pcm, dtype='<i2').astype(np.float32) / 32768.0
    return float(np.sqrt(np.mean(audio * audio))), float(np.max(np.abs(audio)))


def norm_text(text: str) -> str:
    return ' '.join(re.findall(r'[\w]+', (text or '').casefold()))


def is_likely_echo(candidate: str, assistant_text: str) -> bool:
    """Reject near-verbatim fragments of the previous speaker's reply.

    Compare only against recent VORAK speech; NOT generic semantically similar text.
    This method can reject a user deliberately repeating the assistant, which is why
    it is restricted to the speaker-playback interval by TranscriptGuard.
    """
    q = norm_text(candidate)
    a = norm_text(assistant_text)
    if not q or not a or len(q) < 5:
        return False
    if len(q) >= 8 and q in a:
        return True
    if len(q) >= 12:
        tokens = q.split()
        for i in range(max(1, len(a.split()) - len(tokens) + 1)):
            window = ' '.join(a.split()[i:i + len(tokens)])
            if SequenceMatcher(None, q, window).ratio() >= 0.89:
                return True
    return False


class AudioGuard:
    """Realtime voice onset filtering with 480ms pre-roll and adaptive noise floor.

    mode=headset: lower onset gate for barge-in, relies on physical isolation.
    mode=speakers: higher onset threshold during playback, reduces echo risk but
    may miss quiet interruptions. No algorithm can guarantee full-duplex AEC here.
    """
    def __init__(self, mode='speakers', threshold=0.002, rate=16000,
                 frame_ms=40, clock=monotonic, pause_seconds=2.0):
        if mode not in ('speakers', 'headset'):
            raise ValueError('audio mode must be speakers or headset')
        if not (0.001 <= float(threshold) <= 0.05):
            raise ValueError('invalid speech threshold')
        self.mode = mode
        self.threshold = float(threshold)
        if not 1.0 <= pause_seconds <= 6.0: raise ValueError('invalid pause')
        self.pause_seconds = float(pause_seconds)  # VORAK_FOCUS_FIX_V6
        self.rate = rate
        self.frame_ms = frame_ms
        self.clock = clock
        self.lock = threading.RLock()
        self.noise = 0.001
        self.pre = deque(maxlen=12)
        self.candidate = 0
        self.active = False
        self.last_loud = 0.0
        self.last_confirmed = -1e9
        self.playback = False
        self.playback_until = 0.0
        self.last_playback = -1e9
        self.quiet_frames = 0

    def set_playback(self, playing: bool):
        with self.lock:
            self.playback = bool(playing)
            now = self.clock()
            if playing:
                self.last_playback = now
            else:
                # The speaker's final words can linger acoustically.
                self.playback_until = now + (0.35 if self.mode == 'speakers' else 0.08)

    def playback_recent(self) -> bool:
        with self.lock:
            return self.playback or self.clock() < self.playback_until

    def had_user_speech(self, max_age=6.0) -> bool:
        with self.lock:
            return self.clock() - self.last_confirmed <= max_age

    def feed(self, pcm: bytes) -> list[bytes]:
        """Return safe PCM frames for Gemini. Called only by sounddevice callback.

        During detected speech transmit original audio; outside speech transmit
        silence. On a new onset, include the recent pre-roll frames.
        """
        if not isinstance(pcm, bytes) or len(pcm) < 160 or len(pcm) % 2:
            return []
        silence = bytes(len(pcm))
        level, peak = rms_peak(pcm)
        now = self.clock()
        with self.lock:
            loud_playback = self.playback or now < self.playback_until
            floor = max(self.threshold, self.noise * 3.4)
            if loud_playback:
                floor = max(floor, 0.006 if self.mode == 'headset' else 0.018)
            is_voice_energy = level >= floor and peak >= floor * 1.5
            if not self.active and not is_voice_energy and not loud_playback and level < max(0.009, self.noise * 4):
                self.noise = min(0.015, max(0.0003, 0.97 * self.noise + 0.03 * level))
            if not self.active:
                self.pre.append(pcm if is_voice_energy else silence)
                self.candidate = self.candidate + 1 if is_voice_energy else 0
                # The first speech in a quiet room should not be confused with a click.
                required = 3 if not loud_playback or self.mode == 'headset' else 5
                if self.candidate >= required:
                    self.active = True
                    self.last_loud = now
                    self.last_confirmed = now
                    self.quiet_frames = 0
                    frames = list(self.pre)
                    self.pre.clear()
                    return frames
                return [silence]
            # Active speech: configurable thinking pause, default 2 seconds.
            if is_voice_energy:
                self.last_loud = now
                self.last_confirmed = now
                self.quiet_frames = 0
                return [pcm]
            self.quiet_frames += 1
            # Brief low-volume consonants within 240ms of voiced speech are kept.
            if self.quiet_frames <= 6:
                return [pcm]
            if now - self.last_loud > self.pause_seconds + 0.25:
                self.active = False
                self.candidate = 0
                self.pre.clear()
            return [silence]


class TranscriptGuard:
    """Filters only confidently identified short playback echoes from display/ledger.

    This does not grant actions or replace Gemini's final transcript. Source audio
    must first pass AudioGuard, which limits false-positive model activation.
    """
    def __init__(self, audio_guard: AudioGuard, clock=monotonic):
        self.audio_guard = audio_guard
        self.clock = clock
        self.assistant = ''
        self.last_spoken_at = -1e9

    def hear_assistant(self, text: str):
        text = (text or '').strip()
        if text:
            self.assistant = (self.assistant + ' ' + text)[-2400:]
            self.last_spoken_at = self.clock()

    def accept_user(self, text: str) -> bool:
        s = (text or '').strip()
        if not s or not self.audio_guard.had_user_speech(max_age=7.0):
            return False
        if self.clock() - self.last_spoken_at < 12.0 and is_likely_echo(s, self.assistant):
            return False
        return True
