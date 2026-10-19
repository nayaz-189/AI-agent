"""Bounded audio/STT/TTS adapters with synthetic audio; no physical device use."""
import logging
from pathlib import Path
import subprocess
import sys
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock, patch

from voice.audio import AudioClip, AudioIO, VoiceAudioError, validate_audio, _AUDIO_LOCK
from voice.speech import SpeechRecognizer, SpeechOutput, _local_model, MODEL_ROOT


def samples(seconds=2):
    import numpy as np
    return (np.sin(np.arange(int(16000 * seconds)) * 0.06) * 0.15).astype(np.float32)


def rejected(function, code):
    try:
        function()
        assert False, "Operation should fail closed."
    except VoiceAudioError as error:
        assert error.code == code
        assert "SYNTHETIC_PRIVATE" not in str(error)


def segment(text="Open Calculator.", **overrides):
    values = dict(text=text, no_speech_prob=0.02, avg_logprob=-0.2, compression_ratio=1.1)
    values.update(overrides)
    return SimpleNamespace(**values)


def test_import_does_not_load_audio_models_or_open_devices():
    script = """
import sys
import voice.audio, voice.speech
assert not {'sounddevice', 'numpy', 'faster_whisper', 'kokoro_onnx', 'onnxruntime'} & set(sys.modules)
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, timeout=30)
    assert result.returncode == 0


def test_audio_clip_is_immutable_and_repr_hides_samples():
    original = samples()
    clip = AudioClip(original)
    original[:] = 0
    assert validate_audio(clip) is clip
    try:
        clip.samples.setflags(write=True)
        assert False
    except ValueError:
        pass
    assert "samples=" not in repr(clip)


def test_invalid_short_silent_noisy_format_and_clipped_audio_rejected():
    import numpy as np
    for data in (np.zeros(16000, np.float32), np.full(16000, .2, np.float32)):
        rejected(lambda: validate_audio(AudioClip(data)), "no_speech")
    for data in (samples(.2), np.full(16000, float("nan"), np.float32),
                 np.tile(np.array([-1., 1.], np.float32), 8000)):
        rejected(lambda: validate_audio(AudioClip(data)), "invalid_audio")
    for data in (samples().astype(np.float64), samples().reshape(-1, 1), [0.1] * 16000):
        rejected(lambda: AudioClip(data), "invalid_audio")
    rejected(lambda: AudioClip(samples(), sample_rate=48000), "invalid_audio")


def test_capture_is_bounded_and_stream_requests_correct_format():
    stream = Mock()
    stream.__enter__ = Mock(return_value=stream)
    stream.__exit__ = Mock(return_value=False)
    stream.read.side_effect = lambda n: (samples(n / 16000).reshape(-1, 1), False)
    device = Mock(InputStream=Mock(return_value=stream))
    with patch("voice.audio._sounddevice", return_value=device):
        result = AudioIO().capture(seconds=2, input_device=3)
    assert result.samples.size == 32000 and result.sample_rate == 16000
    assert stream.read.call_count == 20
    assert device.InputStream.call_args.kwargs == {"samplerate": 16000, "channels": 1, "dtype": "float32", "device": 3}
    for seconds in (0, 13, True, float("nan")):
        rejected(lambda: AudioIO().capture(seconds), "invalid_settings")


def test_capture_failure_cancel_and_shared_lock_release():
    with patch("voice.audio._sounddevice", side_effect=OSError("SYNTHETIC_PRIVATE")):
        rejected(lambda: AudioIO().capture(), "capture_failed")
    event = Event()
    event.set()
    with patch("voice.audio._sounddevice", return_value=Mock()) as backend:
        rejected(lambda: AudioIO().capture(cancel=event), "cancelled")
        backend.return_value.InputStream.assert_not_called()
    assert _AUDIO_LOCK.acquire(blocking=False)
    try:
        rejected(lambda: AudioIO().capture(), "audio_busy")
        rejected(lambda: AudioIO().play(samples(), 16000), "audio_busy")
    finally:
        _AUDIO_LOCK.release()


def test_playback_volume_chunks_and_cancellation():
    import numpy as np
    stream = Mock()
    stream.__enter__ = Mock(return_value=stream)
    stream.__exit__ = Mock(return_value=False)
    stream.write.return_value = False
    with patch("voice.audio._sounddevice", return_value=Mock(OutputStream=Mock(return_value=stream))):
        AudioIO().play(samples(), 16000, volume=0.5)
    written = np.concatenate([call.args[0].flatten() for call in stream.write.call_args_list])
    assert np.allclose(written, samples() * .5)
    event = Event()
    stream.write.side_effect = lambda chunk: event.set() or False
    with patch("voice.audio._sounddevice", return_value=Mock(OutputStream=Mock(return_value=stream))):
        rejected(lambda: AudioIO().play(samples(), 16000, cancel=event), "cancelled")
    stream.abort.assert_called_once()
    rejected(lambda: AudioIO().play(samples(), 16000, volume=2), "invalid_audio")


def test_device_enumeration_and_errors_are_sanitized():
    device = Mock()
    device.query_devices.return_value = [{"name": "Synthetic microphone", "max_input_channels": 1, "max_output_channels": 0}]
    with patch("voice.audio._sounddevice", return_value=device):
        assert AudioIO().list_devices() == [{"id": 0, "name": "Synthetic microphone", "input_channels": 1, "output_channels": 0}]
    with patch("voice.audio._sounddevice", side_effect=OSError("SYNTHETIC_PRIVATE")):
        rejected(lambda: AudioIO().list_devices(), "device_unavailable")


def test_transcription_valid_normal_slang_and_privacy():
    recognizer = SpeechRecognizer()
    model = Mock()
    for text in ("Open Calculator.", "Yo Vorak, pull up Calculator.", "Bro, open the calculator."):
        model.transcribe.return_value = (iter([segment(text)]), object())
        with patch.object(recognizer, "_load", return_value=model):
            result = recognizer.transcribe(AudioClip(samples()))
        assert result.text == text and result.confident and result.latency_ms >= 0
        assert text not in repr(result)
    assert model.transcribe.call_args.kwargs["vad_filter"] is True


def test_uncertain_empty_and_background_transcripts_fail_closed():
    recognizer = SpeechRecognizer()
    for bad in ([], [segment("")], [segment(no_speech_prob=.9)],
                [segment(avg_logprob=-2)], [segment(compression_ratio=3)],
                [segment(avg_logprob=float("nan"))], [segment("x" * 601)]):
        model = Mock()
        model.transcribe.return_value = (iter(bad), object())
        with patch.object(recognizer, "_load", return_value=model):
            rejected(lambda: recognizer.transcribe(AudioClip(samples())), "uncertain_transcription")
    import numpy as np
    with patch.object(recognizer, "_load") as load:
        rejected(lambda: recognizer.transcribe(AudioClip(np.zeros(16000, np.float32))), "no_speech")
    load.assert_not_called()


def test_transcription_backend_error_and_debug_logging_are_private():
    recognizer = SpeechRecognizer()
    model = Mock()
    def fail(*args, **kwargs):
        logging.getLogger("faster_whisper").debug("SYNTHETIC_PRIVATE")
        raise OSError("SYNTHETIC_PRIVATE")
    model.transcribe.side_effect = fail
    handler = Mock(spec=logging.Handler)
    handler.level = logging.DEBUG
    logger = logging.getLogger("faster_whisper")
    previous = logger.level
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:
        with patch.object(recognizer, "_load", return_value=model):
            rejected(lambda: recognizer.transcribe(AudioClip(samples())), "transcription_failed")
        handler.handle.assert_not_called()
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)


def test_models_require_confined_existing_files_and_never_download():
    rejected(lambda: _local_model(Path("C:/unapproved/model.onnx")), "model_unavailable")
    rejected(lambda: _local_model(MODEL_ROOT / "../unapproved.onnx"), "model_unavailable")
    rejected(lambda: _local_model(MODEL_ROOT / "synthetic-missing.onnx"), "model_unavailable")
    constructor = Mock(return_value=Mock())
    with patch("voice.speech._local_model", return_value="synthetic-local-cache"), \
            patch("voice.speech._verify_assets"), \
            patch.dict(sys.modules, {"faster_whisper": SimpleNamespace(WhisperModel=constructor)}):
        recognizer = SpeechRecognizer()
        assert recognizer._load() is recognizer._load()
    assert constructor.call_count == 1
    assert constructor.call_args.kwargs == {"device": "cpu", "compute_type": "int8", "cpu_threads": 2,
                                           "num_workers": 1, "local_files_only": True}


def test_two_voice_profiles_rate_validation_and_cached_backend():
    output = SpeechOutput()
    model = Mock()
    model.create.return_value = (samples(), 16000)
    output._model = model
    for profile, voice in (("male", "am_michael"), ("female", "af_sarah")):
        audio, rate = output.synthesize("A short synthetic preview.", profile, 1.1)
        assert audio.size == 32000 and rate == 16000
        assert model.create.call_args.kwargs["voice"] == voice
        assert model.create.call_args.kwargs["speed"] == 1.1
    assert output.last_latency_ms >= 0
    for profile, rate in (("unknown", 1), ("male", 3), ("female", float("nan"))):
        rejected(lambda: output.synthesize("Preview.", profile, rate), "invalid_settings")


def test_synthesis_error_audio_limits_and_debug_privacy():
    output = SpeechOutput()
    def fail(*args, **kwargs):
        logging.getLogger("kokoro_onnx").debug("SYNTHETIC_PRIVATE")
        raise OSError("SYNTHETIC_PRIVATE")
    output._model = Mock(create=Mock(side_effect=fail))
    handler = Mock(spec=logging.Handler)
    handler.level = logging.DEBUG
    logger = logging.getLogger("kokoro_onnx")
    previous = logger.level
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:
        rejected(lambda: output.synthesize("Preview."), "synthesis_failed")
        handler.handle.assert_not_called()
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)
    import numpy as np
    output._model = Mock(create=Mock(return_value=(np.array([float("nan")], np.float32), 24000)))
    rejected(lambda: output.synthesize("Preview."), "synthesis_failed")
    rejected(lambda: output.synthesize("x" * 1201), "invalid_settings")


def test_close_releases_cached_models_and_voice_archive():
    recognizer, output = SpeechRecognizer(), SpeechOutput()
    recognizer._model = Mock()
    model = output._model = Mock()
    recognizer.close()
    output.close()
    assert recognizer._model is None and output._model is None
    model.voices.close.assert_called_once()


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
    print(f"Voice audio adapter tests: {len(tests)} passed (synthetic audio; physical tests not run).")
