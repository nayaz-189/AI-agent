"""Owner-gated voice composition. All OS actions use the existing VORAK runtime."""
from collections import deque
from dataclasses import dataclass, field, replace
from copy import deepcopy
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from threading import Lock
import time
from uuid import uuid4

from desktop.confirmation_authority import ConfirmationAuthority
from desktop.user_confirmation import UserConfirmationBoundary
from execution.execution_history import ExecutionHistory
from voice.audio import AudioIO, VoiceAudioError, validate_audio
from voice.dialogue import DialogueSession, IntentKind, classify_intent, parse_wake
from voice.identity import SpeakerOutcome, Verification
from voice.owner_upgrade import UpgradedSpeakerVerifier as SpeakerVerifier
from voice.settings import MODEL_ROOT, VOICE_ROOT, SettingsStore
from voice.speech import SpeechRecognizer, SpeechOutput, Transcription


# Physical owner acceptance failed during Day 18 testing. This reviewed default
# denial is deliberately not a preference, environment flag or planner input.
# Enable only after a new reviewed physical acceptance/calibration validation.
VOICE_ACTIONS_READY = False


def confirm_voice_request(request):
    """Real local application-permission dialog; not voice or OS authentication."""
    if os.name != "nt" or type(request) is not dict:
        return False
    actions = {"voice_open_calculator": "Open Windows Calculator after this voice request",
               "enroll_voice_owner": "Create the first experimental local owner voice profile",
               "upgrade_voice_owner": "Create an additional 15-sample owner profile, keeping the original untouched",
               "calibrate_voice_owner": "Calibrate the owner profile with owner and consenting non-owner samples"}
    if request.get("action") not in actions:
        return False
    proposal = json.dumps(request, sort_keys=True, ensure_ascii=True)
    if len(proposal) > 6000:
        return False
    message = (actions[request["action"]] + ".\n\nSpeaker similarity does not prove liveness. "
               "Approve only your own intended action. No or timeout cancels.\n\nExact bound proposal:\n" + proposal)
    try:
        dialog = ctypes.windll.user32.MessageBoxTimeoutW
        dialog.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR,
                           wintypes.UINT, wintypes.WORD, wintypes.DWORD]
        dialog.restype = ctypes.c_int
        return dialog(None, message, "VORAK voice permission", 0x4 | 0x20 | 0x100 | 0x10000, 0, 20000) == 6
    except Exception:
        return False


def obtain_confirmation(authority, request, interface=confirm_voice_request):
    """Only trusted composition calls this after presenting the exact proposal."""
    approved = interface(deepcopy(request)) is True
    decision = UserConfirmationBoundary(authority).process_user_decision(request, approved)
    confirmation = decision.get("confirmation")
    return confirmation.token if confirmation is not None else None


@dataclass(frozen=True)
class VoiceReply:
    text: str = field(repr=False)
    outcome: str
    verified: bool = False


class VoiceRuntime:
    """Injected adapters are trusted test/composition seams, never planner inputs."""
    def __init__(self, *, audio=None, recognizer=None, verifier=None, speech=None,
                 settings_store=None, confirmation_ui=None, clock=time.monotonic):
        self.store = settings_store or SettingsStore()
        self.settings = self.store.load()
        self.audio = audio or AudioIO()
        self.recognizer = recognizer or SpeechRecognizer()
        self.verifier = verifier or SpeakerVerifier(MODEL_ROOT / "ecapa" / "embedding_model.ckpt", VOICE_ROOT / "identity")
        self.speech = speech or SpeechOutput()
        self.dialogue = DialogueSession(self.settings.conversation_timeout_seconds, clock=clock)
        self.history = ExecutionHistory()
        self.authority = ConfirmationAuthority(ttl_seconds=15)
        self.confirmation_ui = confirmation_ui or confirm_voice_request
        self._clock = clock
        self._session_id = None
        self._busy = Lock()
        self._diagnostics = deque(maxlen=64)

    @property
    def diagnostics(self):
        return tuple(dict(item) for item in self._diagnostics)

    def _measure(self, stage, function):
        start = time.perf_counter()
        try:
            result = function()
        except Exception:
            self._diagnostics.append({"stage": stage, "status": "failed",
                                      "milliseconds": round((time.perf_counter() - start) * 1000, 2)})
            raise
        self._diagnostics.append({"stage": stage, "status": "completed",
                                  "milliseconds": round((time.perf_counter() - start) * 1000, 2)})
        return result

    def stop_session(self):
        self.dialogue.stop()
        self._session_id = None

    def _fresh(self, clip, verdict):
        return (type(verdict) is Verification and verdict.outcome is SpeakerOutcome.OWNER_VERIFIED
                and verdict.captured_at == clip.captured_at
                and verdict.audio_digest == hashlib.sha256(clip.samples.astype("<f4", copy=False).tobytes()).hexdigest()
                and 0 <= self._clock() - clip.captured_at <= 30)

    def process_clip(self, clip, *, push_to_talk=False, cancel=None):
        """One fresh recording, no serialized owner flags or spoken approval."""
        if not self._busy.acquire(blocking=False):
            return VoiceReply("Voice processing is busy.", "blocked")
        started = time.perf_counter()
        try:
            # A receipt is needed only for the current request, not indefinitely.
            self.history.clear()
            return self._process(clip, push_to_talk=push_to_talk, cancel=cancel)
        except VoiceAudioError as error:
            return VoiceReply(str(VoiceAudioError(getattr(error, "code", None))), "audio_unavailable")
        except Exception:
            return VoiceReply("Voice processing is unavailable. No completion was verified.", "unavailable")
        finally:
            self._diagnostics.append({"stage": "total", "status": "finished",
                                      "milliseconds": round((time.perf_counter() - started) * 1000, 2)})
            self._busy.release()

    def _process(self, clip, *, push_to_talk, cancel):
        if type(push_to_talk) is not bool:
            return VoiceReply("Listening activation is invalid.", "blocked")
        self._measure("audio_quality", lambda: validate_audio(clip))
        verdict = self._measure("speaker_verification", lambda: self.verifier.verify(clip))
        if not self._fresh(clip, verdict):
            self.stop_session()
            return VoiceReply("I couldn't verify the enrolled owner. No action was performed.", "owner_unverified")
        if cancel is not None and cancel.is_set():
            return VoiceReply("Voice request cancelled before execution.", "cancelled")
        transcription = self._measure("transcription", lambda: self.recognizer.transcribe(clip))
        if type(transcription) is not Transcription or transcription.confident is not True:
            return VoiceReply("The transcript is uncertain. Please repeat it.", "uncertain")
        wake = parse_wake(transcription.text, active=self.dialogue.active)
        if not (push_to_talk or wake.activated):
            return VoiceReply("Activate push-to-talk or address VORAK explicitly.", "inactive")
        if not self.dialogue.active:
            self.dialogue.start()
            self._session_id = str(uuid4())
        text = wake.text
        if not text:
            return VoiceReply("I'm listening. Press Enter when you're ready to speak.", "conversation")
        intent = self._measure("intent", lambda: classify_intent(text))
        if intent.kind is IntentKind.CANCEL:
            self.stop_session()
            return VoiceReply("Conversation stopped. This does not undo an action already executed.", "cancelled")
        if intent.kind is IntentKind.CONFIRMATION:
            return VoiceReply("Spoken approval cannot authorize an action. Use the local permission dialog.", "blocked")
        if intent.kind is IntentKind.SETTING:
            name, value = intent.setting
            if name != "voice_profile":
                return VoiceReply("That voice setting is unavailable.", "unsupported")
            settings = replace(self.settings, voice_profile=value)
            self.store.save(settings)
            self.settings = settings
            return VoiceReply("Voice preference saved.", "setting")
        if intent.kind in {IntentKind.UNSUPPORTED, IntentKind.AMBIGUOUS}:
            return VoiceReply("I haven't acted on that. Voice actions currently support an explicit Calculator request only.", "unsupported")
        if intent.kind is not IntentKind.ACTION:
            return VoiceReply(self._measure("local_dialogue", lambda: self.dialogue.respond(
                text, personality_style=self.settings.personality_style,
                profanity_level=self.settings.profanity_level)), "conversation")

        if VOICE_ACTIONS_READY is not True:
            return VoiceReply("Voice actions are disabled pending successful physical owner and non-owner acceptance checks.", "blocked")

        from brain.planner import understand_command
        from brain.validator import validate_plan
        from execution.runtime import execute_plan
        plan = self._measure("planning", lambda: understand_command(intent.command))
        if (type(plan) is not dict or plan != {"tool": "open_calculator", "arguments": {}}
                or not validate_plan(plan) or not self._fresh(clip, verdict) or not self.dialogue.active):
            return VoiceReply("The voice action failed validation. Nothing was executed.", "blocked")
        request = {"action": "voice_open_calculator", "plan": deepcopy(plan),
                   "session_id": self._session_id, "capture_digest": verdict.audio_digest,
                   "captured_at": clip.captured_at}
        token = self._measure("local_confirmation", lambda: obtain_confirmation(
            self.authority, request, self.confirmation_ui))
        authorized = self.authority.consume(token, request).get("confirmed") is True
        if (not self._fresh(clip, verdict) or not self.dialogue.active or
                (cancel is not None and cancel.is_set()) or
                not authorized):
            return VoiceReply("The action was not authorized or its voice session expired.", "blocked")
        task = self._measure("execution_verification", lambda: execute_plan(
            "Open Calculator", deepcopy(plan), history=self.history))
        if self.history.has_verification(task, "calculator"):
            return VoiceReply("Calculator's up. I verified its window.", "completed", True)
        return VoiceReply("I couldn't independently verify Calculator. I won't report it as completed.", "unverified")

    def capture(self, *, seconds=5, cancel=None):
        return self._measure("capture", lambda: self.audio.capture(
            seconds=seconds, input_device=self.settings.microphone_device, cancel=cancel))

    def speak(self, reply, *, cancel=None):
        if type(reply) is not VoiceReply:
            raise ValueError("Invalid speech response.")
        if cancel is not None and cancel.is_set():
            return
        samples, sample_rate = self._measure("speech_synthesis", lambda: self.speech.synthesize(
            reply.text, profile=self.settings.voice_profile, rate=self.settings.speech_rate))
        if cancel is not None and cancel.is_set():
            return
        self._measure("playback", lambda: self.audio.play(
            samples, sample_rate, volume=self.settings.volume,
            output_device=self.settings.speaker_device, cancel=cancel))
