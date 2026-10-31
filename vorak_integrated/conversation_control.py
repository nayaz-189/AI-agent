"""Deterministic local speech-state gate for VORAK.

Speech controls only: never cancel desktop actions or research jobs.
No credentials, network access or OS operations.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import time

_STOP_WORDS = re.compile(
    r"(?i)^(?:hey\s+)?(?:v(?:orak)?[,\s]+)?(?:stop(?:\s+(?:speaking|talking|the\s+answer))?|be\s+quiet|shut\s+up)[.!\s]*$"
)

def is_stop_utterance(transcript: str) -> bool:
    return bool(_STOP_WORDS.fullmatch(' '.join(str(transcript or '').strip().split())))


_PAUSE_WORDS = re.compile(
    r"(?i)^(?:hey[, ]+)?(?:v(?:orak)?[,]?\s+)?(?:please\s+)?"
    r"(?:pause|wait|give\s+me|hold\s+on)\s+(?:for\s+)?"
    r"(10|20|30|ten|twenty|thirty)\s*(?:seconds?|secs?)\b"
)
_PAUSE_NUMBERS = {"10": 10, "ten": 10, "20": 20, "twenty": 20,
                  "30": 30, "thirty": 30}


def parse_pause_utterance(transcript: str) -> int | None:
    """Only an explicit turn-opening request, not an arbitrary mention of time."""
    text = ' '.join(str(transcript or '').strip().split())
    m = _PAUSE_WORDS.match(text)
    return _PAUSE_NUMBERS.get(m.group(1).casefold()) if m else None


@dataclass
class ConversationGate:
    """State transitions are safe to evaluate in the asyncio receiver loop."""
    mode: str = "active"          # active | stopped | holding
    deadline: float = 0.0
    generation: int = 0

    def should_play(self) -> bool:
        return self.mode == "active"

    def stop(self) -> dict:
        self.generation += 1
        self.mode = "stopped"
        self.deadline = 0.0
        return {"status": "speech_stopped", "message": "Speech stopped. Waiting for a new command. No task was cancelled."}

    def hold(self, seconds: int, *, now: float | None = None) -> dict:
        if type(seconds) is not int or seconds not in (10, 20, 30):
            return {"status": "invalid", "message": "Choose 10, 20, or 30 seconds."}
        self.generation += 1
        self.mode = "holding"
        self.deadline = (time.monotonic() if now is None else now) + seconds
        return {"status": "speech_paused", "seconds": seconds,
                "message": "Speech paused. Listening for follow-up questions until the timer ends; tasks are not cancelled."}

    def resume(self) -> dict:
        was = self.mode
        self.generation += 1
        self.mode = "active"
        self.deadline = 0.0
        return {"status": "speech_resumed" if was != "active" else "already_active",
                "message": "Ready to answer."}

    def is_current_hold(self, token: int, *, now: float | None = None) -> bool:
        t = time.monotonic() if now is None else now
        return self.mode == "holding" and self.generation == token and t >= self.deadline

    def new_user_utterance(self, transcript: str) -> bool:
        """New real speech releases STOP, but not a timed HOLD.

        Transcript is only a convenience hint: not authentication, not
        a substitute for Gemini's server-side VAD.
        """
        if self.mode != "stopped":
            return False
        value = " ".join(str(transcript or "").strip().split())
        if len(value) < 4 or is_stop_utterance(value):
            return False
        self.resume()
        return True
