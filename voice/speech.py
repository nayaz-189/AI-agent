"""Lazy local-only speech adapters. No model download, capture or playback on import."""
from dataclasses import dataclass, field
from contextlib import contextmanager
import logging
import math
from pathlib import Path
import stat
from threading import Lock
from time import perf_counter

from voice.audio import VoiceAudioError, _finite_number, _numpy, validate_audio


MODEL_ROOT = Path(__file__).resolve().parents[1] / "runtime" / "voice" / "models"
WHISPER_DIRECTORY = MODEL_ROOT / "whisper-tiny.en"
KOKORO_MODEL = MODEL_ROOT / "kokoro-v1.0.onnx"
KOKORO_VOICES = MODEL_ROOT / "voices-v1.0.bin"
_RECOGNITION_LOCK = Lock()
_SYNTHESIS_LOCK = Lock()


@contextmanager
def _quiet_loggers(*names):
    loggers = [logging.getLogger(name) for name in names]
    previous = [logger.disabled for logger in loggers]
    try:
        for logger in loggers:
            logger.disabled = True
        yield
    finally:
        for logger, disabled in zip(loggers, previous):
            logger.disabled = disabled


def _local_model(path, *, directory=False):
    """Only the explicitly provisioned project cache; never follow redirected paths."""
    candidate = Path(path).absolute()
    if not candidate.is_relative_to(MODEL_ROOT) or ".." in candidate.parts:
        raise VoiceAudioError("model_unavailable")
    try:
        file_info = candidate.lstat()
        for parent in (candidate, *candidate.parents):
            info = parent.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise VoiceAudioError("model_unavailable")
        if directory:
            if not candidate.is_dir():
                raise VoiceAudioError("model_unavailable")
            for name in ("model.bin", "config.json", "tokenizer.json"):
                _local_model(candidate / name)
        elif not candidate.is_file() or file_info.st_nlink != 1:
            raise VoiceAudioError("model_unavailable")
    except (OSError, ValueError):
        raise VoiceAudioError("model_unavailable") from None
    return str(candidate)


def _verify_assets(kind):
    try:
        from voice.models import verify_model_assets
        verify_model_assets(kind)
    except Exception:
        raise VoiceAudioError("model_unavailable") from None


@dataclass(frozen=True)
class Transcription:
    text: str = field(repr=False)
    latency_ms: float
    confident: bool = True


class SpeechRecognizer:
    def __init__(self, model_path=WHISPER_DIRECTORY):
        self._path, self._model, self._lock = model_path, None, _RECOGNITION_LOCK

    def _load(self):
        if self._model is None:
            if Path(self._path).absolute() != WHISPER_DIRECTORY:
                raise VoiceAudioError("model_unavailable")
            path = _local_model(self._path, directory=True)
            _verify_assets("whisper")
            try:
                from faster_whisper import WhisperModel
                self._model = WhisperModel(path, device="cpu", compute_type="int8",
                                           cpu_threads=2, num_workers=1, local_files_only=True)
            except Exception:
                raise VoiceAudioError("model_unavailable") from None
        return self._model

    def close(self):
        if not self._lock.acquire(blocking=False):
            raise VoiceAudioError("audio_busy")
        try:
            self._model = None
        finally:
            self._lock.release()

    def transcribe(self, clip):
        validate_audio(clip)
        if not self._lock.acquire(blocking=False):
            raise VoiceAudioError("audio_busy")
        started = perf_counter()
        try:
            # Faster Whisper can otherwise log recognized words at DEBUG level.
            with _quiet_loggers("faster_whisper"):
                segments, _ = self._load().transcribe(
                    clip.samples, language="en", beam_size=1, vad_filter=True,
                    condition_on_previous_text=False, max_new_tokens=128,
                    vad_parameters={"min_silence_duration_ms": 400})
                parts = []
                for index, segment in enumerate(segments):
                    if index >= 32:
                        raise VoiceAudioError("uncertain_transcription")
                    values = (segment.no_speech_prob, segment.avg_logprob, segment.compression_ratio)
                    if any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in values):
                        raise VoiceAudioError("uncertain_transcription")
                    if values[0] > 0.6 or values[1] < -1.0 or values[2] > 2.4:
                        raise VoiceAudioError("uncertain_transcription")
                    if type(segment.text) is not str:
                        raise VoiceAudioError("uncertain_transcription")
                    parts.append(segment.text.strip())
                text = " ".join(parts).strip()
            if not text or len(text) > 600 or any(ord(char) < 32 for char in text):
                raise VoiceAudioError("uncertain_transcription")
            return Transcription(text, round((perf_counter() - started) * 1000, 2))
        except VoiceAudioError:
            raise
        except Exception:
            raise VoiceAudioError("transcription_failed") from None
        finally:
            self._lock.release()


class SpeechOutput:
    """Two neural profiles; unavailable assets fail explicitly, never silently downgrade."""
    PROFILES = {"male": "am_michael", "female": "af_sarah"}

    def __init__(self, model_path=KOKORO_MODEL, voices_path=KOKORO_VOICES):
        self._model_path, self._voices_path = model_path, voices_path
        self._model, self._lock = None, _SYNTHESIS_LOCK
        self.last_latency_ms = None

    def _load(self):
        if self._model is None:
            if (Path(self._model_path).absolute() != KOKORO_MODEL or
                    Path(self._voices_path).absolute() != KOKORO_VOICES):
                raise VoiceAudioError("model_unavailable")
            model, voices = _local_model(self._model_path), _local_model(self._voices_path)
            _verify_assets("kokoro")
            try:
                import onnxruntime as ort
                from kokoro_onnx import Kokoro
                options = ort.SessionOptions()
                options.intra_op_num_threads = 2
                options.inter_op_num_threads = 1
                session = ort.InferenceSession(model, sess_options=options, providers=["CPUExecutionProvider"])
                self._model = Kokoro.from_session(session, voices)
                if not set(self.PROFILES.values()).issubset(set(self._model.get_voices())):
                    self._model = None
                    raise VoiceAudioError("model_unavailable")
            except Exception:
                raise VoiceAudioError("model_unavailable") from None
        return self._model

    def close(self):
        if not self._lock.acquire(blocking=False):
            raise VoiceAudioError("audio_busy")
        try:
            model, self._model = self._model, None
            if model is not None:
                model.voices.close()
        except Exception:
            raise VoiceAudioError("synthesis_failed") from None
        finally:
            self._lock.release()

    def synthesize(self, text, profile="male", rate=1.0):
        if (type(text) is not str or not text.strip() or len(text) > 1200 or
                any(ord(char) < 32 and char not in "\n\t" for char in text) or
                type(profile) is not str or profile not in self.PROFILES or
                not _finite_number(rate, 0.75, 1.5)):
            raise VoiceAudioError("invalid_settings")
        if not self._lock.acquire(blocking=False):
            raise VoiceAudioError("audio_busy")
        started = perf_counter()
        try:
            # The neural backend's DEBUG logs can include text-derived phonemes.
            with _quiet_loggers("kokoro_onnx", "phonemizer"):
                samples, sample_rate = self._load().create(
                    text.strip(), voice=self.PROFILES[profile], speed=float(rate), lang="en-us")
            np = _numpy()
            samples = np.asarray(samples, dtype=np.float32)
            if (type(sample_rate) is not int or not 8000 <= sample_rate <= 48000 or
                    samples.ndim != 1 or not 1 <= samples.size <= sample_rate * 60 or
                    not np.isfinite(samples).all() or np.max(np.abs(samples)) > 1):
                raise VoiceAudioError("synthesis_failed")
            self.last_latency_ms = round((perf_counter() - started) * 1000, 2)
            return samples, sample_rate
        except VoiceAudioError:
            raise
        except Exception:
            raise VoiceAudioError("synthesis_failed") from None
        finally:
            self._lock.release()
