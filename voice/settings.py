"""Closed cosmetic settings; identity and action authority are never preferences."""
from dataclasses import asdict, dataclass, fields
import json
import math
import os
from pathlib import Path
import secrets

from execution.device_storage import private_directory, private_create, private_read


VOICE_ROOT = Path(__file__).resolve().parent.parent / "runtime" / "voice"
MODEL_ROOT = VOICE_ROOT / "models"


class SettingsError(RuntimeError):
    def __init__(self):
        super().__init__("Voice settings are unavailable or invalid.")


@dataclass(frozen=True)
class VoiceSettings:
    voice_profile: str = "male"
    personality_style: str = "adaptive"
    profanity_level: str = "natural"
    speech_rate: float = 1.0
    volume: float = 1.0
    conversation_timeout_seconds: int = 30
    microphone_device: int | None = None
    speaker_device: int | None = None

    def __post_init__(self):
        if (any(type(value) is not str for value in
                (self.voice_profile, self.personality_style, self.profanity_level))
                or self.voice_profile not in {"male", "female"}
                or self.personality_style not in {"adaptive", "playful", "direct", "professional"}
                or self.profanity_level not in {"off", "mild", "natural", "strong"}):
            raise SettingsError()
        for value, low, high in ((self.speech_rate, 0.75, 1.35), (self.volume, 0.0, 1.0)):
            if type(value) not in (float, int) or not math.isfinite(value) or not low <= value <= high:
                raise SettingsError()
        if type(self.conversation_timeout_seconds) is not int or not 10 <= self.conversation_timeout_seconds <= 60:
            raise SettingsError()
        for device in (self.microphone_device, self.speaker_device):
            if device is not None and (type(device) is not int or not 0 <= device <= 1024):
                raise SettingsError()

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) != {field.name for field in fields(cls)}:
            raise SettingsError()
        try:
            return cls(**value)
        except (TypeError, ValueError):
            raise SettingsError() from None


def initialize_storage(root=VOICE_ROOT):
    root = private_directory(root, create=True)
    for name in ("identity", "models"):
        private_directory(root / name, create=True)
    return root


class SettingsStore:
    def __init__(self, root=VOICE_ROOT):
        self.root = Path(root)

    def load(self):
        if not self.root.exists():
            return VoiceSettings()
        try:
            private_directory(self.root)
            if not (self.root / "settings.json").exists():
                return VoiceSettings()

            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise SettingsError()
                    result[key] = value
                return result

            data = json.loads(private_read(self.root, "settings.json"), object_pairs_hook=unique)
            return VoiceSettings.from_dict(data)
        except Exception:
            raise SettingsError() from None

    def save(self, settings):
        if type(settings) is not VoiceSettings:
            raise SettingsError()
        temporary = None
        try:
            initialize_storage(self.root)
            self.load()  # Existing corrupt/insecure settings are never silently replaced.
            name = "settings-" + secrets.token_hex(12) + ".tmp"
            temporary = self.root / name
            private_create(self.root, name, json.dumps(asdict(settings), allow_nan=False).encode())
            os.replace(temporary, self.root / "settings.json")
            if self.load() != settings:
                raise SettingsError()
        except Exception:
            raise SettingsError() from None
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()  # Only this call's newly created temporary file.
