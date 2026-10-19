"""Explicit, bounded in-memory audio. Importing this module opens no device."""
from dataclasses import dataclass, field
import math
from threading import Lock
from time import monotonic


SAMPLE_RATE = 16000
MAX_CAPTURE_SECONDS = 12
MAX_PLAYBACK_SECONDS = 60
_AUDIO_LOCK = Lock()  # Capture and playback exclude one another across instances.
_MESSAGES = {
    "dependency_unavailable": "An optional audio dependency is unavailable.",
    "invalid_audio": "Audio format or recording quality is invalid.",
    "no_speech": "No usable speech was detected.",
    "audio_busy": "Audio capture or playback is already active.",
    "cancelled": "Audio operation cancelled.",
    "capture_failed": "Microphone capture failed; check the selected input device.",
    "playback_failed": "Audio playback failed; check the selected output device.",
    "device_unavailable": "Audio device enumeration failed.",
    "model_unavailable": "The configured local speech model is unavailable.",
    "transcription_failed": "Local speech transcription failed.",
    "uncertain_transcription": "Speech transcription was uncertain; repeat the request.",
    "synthesis_failed": "Local speech synthesis failed.",
    "invalid_settings": "Audio settings are invalid.",
}


class VoiceAudioError(RuntimeError):
    def __init__(self, code):
        self.code = code if type(code) is str and code in _MESSAGES else "invalid_audio"
        super().__init__(_MESSAGES[self.code])


def _numpy():
    try:
        import numpy
        return numpy
    except Exception:
        raise VoiceAudioError("dependency_unavailable") from None


def _sounddevice():
    try:
        import sounddevice
        return sounddevice
    except Exception:
        raise VoiceAudioError("dependency_unavailable") from None


def _finite_number(value, minimum, maximum):
    return type(value) in (int, float) and math.isfinite(value) and minimum <= value <= maximum


def _device(value):
    if value is not None and (type(value) is not int or not 0 <= value <= 65535):
        raise VoiceAudioError("invalid_settings")
    return value


@dataclass(frozen=True)
class AudioClip:
    samples: object = field(repr=False)
    sample_rate: int = SAMPLE_RATE
    captured_at: float = field(default_factory=monotonic)

    def __post_init__(self):
        np = _numpy()
        if (type(self.samples) is not np.ndarray or self.samples.dtype != np.float32
                or self.samples.ndim != 1 or not 1 <= self.samples.size <= SAMPLE_RATE * MAX_CAPTURE_SECONDS
                or type(self.sample_rate) is not int or self.sample_rate != SAMPLE_RATE
                or not _finite_number(self.captured_at, 0, 1e12)):
            raise VoiceAudioError("invalid_audio")
        # Immutable byte backing prevents callers from re-enabling array writes.
        copied = np.frombuffer(self.samples.tobytes(), dtype=np.float32)
        object.__setattr__(self, "samples", copied)


def validate_audio(clip):
    """Reject silence, clipping, DC and malformed audio; this is not speaker VAD."""
    np = _numpy()
    if type(clip) is not AudioClip or clip.sample_rate != SAMPLE_RATE:
        raise VoiceAudioError("invalid_audio")
    samples = clip.samples
    if (samples.dtype != np.float32 or samples.ndim != 1 or
            not SAMPLE_RATE <= samples.size <= SAMPLE_RATE * MAX_CAPTURE_SECONDS or
            not np.isfinite(samples).all() or np.max(np.abs(samples)) > 1):
        raise VoiceAudioError("invalid_audio")
    if float(np.sqrt(np.mean(samples ** 2))) < 0.005 or float(np.std(samples)) < 0.003:
        raise VoiceAudioError("no_speech")
    if float(np.mean(np.abs(samples) >= 0.995)) > 0.05:
        raise VoiceAudioError("invalid_audio")
    return clip


class AudioIO:
    def list_devices(self):
        try:
            devices = _sounddevice().query_devices()
            return [{"id": i, "name": str(item["name"])[:120],
                     "input_channels": int(item["max_input_channels"]),
                     "output_channels": int(item["max_output_channels"])}
                    for i, item in enumerate(devices)]
        except VoiceAudioError:
            raise
        except Exception:
            raise VoiceAudioError("device_unavailable") from None

    def capture(self, seconds=5, input_device=None, cancel=None):
        if not _finite_number(seconds, 1, MAX_CAPTURE_SECONDS):
            raise VoiceAudioError("invalid_settings")
        device = _device(input_device)
        if not _AUDIO_LOCK.acquire(blocking=False):
            raise VoiceAudioError("audio_busy")
        try:
            np, sd = _numpy(), _sounddevice()
            if cancel is not None and cancel.is_set():
                raise VoiceAudioError("cancelled")
            frames, chunks = int(seconds * SAMPLE_RATE), []
            # Ask PortAudio for 16 kHz directly. Unsupported formats fail rather
            # than relabeling 44.1/48 kHz samples or using an incorrect resampler.
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", device=device) as stream:
                while frames:
                    if cancel is not None and cancel.is_set():
                        stream.abort()
                        raise VoiceAudioError("cancelled")
                    count = min(frames, 1600)
                    data, overflow = stream.read(count)
                    if overflow or data.shape != (count, 1):
                        raise VoiceAudioError("capture_failed")
                    chunks.append(data[:, 0].copy())
                    frames -= count
            return validate_audio(AudioClip(np.concatenate(chunks), captured_at=monotonic()))
        except VoiceAudioError:
            raise
        except KeyboardInterrupt:
            raise VoiceAudioError("cancelled") from None
        except Exception:
            raise VoiceAudioError("capture_failed") from None
        finally:
            _AUDIO_LOCK.release()

    def play(self, samples, sample_rate, volume=1.0, output_device=None, cancel=None):
        np = _numpy()
        if (type(sample_rate) is not int or not 8000 <= sample_rate <= 48000 or
                type(samples) is not np.ndarray or samples.dtype != np.float32 or samples.ndim != 1 or
                not 1 <= samples.size <= sample_rate * MAX_PLAYBACK_SECONDS or
                not np.isfinite(samples).all() or np.max(np.abs(samples)) > 1 or
                not _finite_number(volume, 0, 1)):
            raise VoiceAudioError("invalid_audio")
        device = _device(output_device)
        if not _AUDIO_LOCK.acquire(blocking=False):
            raise VoiceAudioError("audio_busy")
        try:
            if cancel is not None and cancel.is_set():
                raise VoiceAudioError("cancelled")
            with _sounddevice().OutputStream(samplerate=sample_rate, channels=1, dtype="float32", device=device) as stream:
                for offset in range(0, samples.size, 1024):
                    if cancel is not None and cancel.is_set():
                        stream.abort()
                        raise VoiceAudioError("cancelled")
                    if stream.write((samples[offset:offset + 1024] * volume).reshape(-1, 1)):
                        raise VoiceAudioError("playback_failed")
        except VoiceAudioError:
            raise
        except KeyboardInterrupt:
            raise VoiceAudioError("cancelled") from None
        except Exception:
            raise VoiceAudioError("playback_failed") from None
        finally:
            _AUDIO_LOCK.release()
