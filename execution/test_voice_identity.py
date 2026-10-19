"""Synthetic owner-verification regressions; no microphones or real identities."""
from contextlib import contextmanager
import json
import math
from pathlib import Path
import tempfile
import time
from unittest.mock import patch

import numpy as np

from desktop.confirmation_authority import ConfirmationAuthority
from execution.device_storage import private_directory
from voice.audio import AudioClip
from voice.identity import IdentityError, SpeakerOutcome, SpeakerVerifier, _digest


def clip(seed, *, seconds=2.1, captured_at=None):
    samples = (0.12 * np.sin(np.arange(int(16000 * seconds), dtype=np.float32)
                            * (0.04 + seed * 0.003))).astype(np.float32)
    return AudioClip(samples, captured_at=time.monotonic() if captured_at is None else captured_at)


def vector(score):
    return [score, math.sqrt(1 - score * score)] + [0.0] * 190


@contextmanager
def fixture(*, enrolled=True, calibrated=True):
    root = Path(__file__).resolve().parents[1] / "runtime" / "voice_identity_tests"
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root) as temporary:
        directory = Path(temporary) / "identity"
        private_directory(directory, create=True)
        with patch("voice.identity.IDENTITY_ROOT", directory):
            verifier = SpeakerVerifier(Path(temporary) / "embedding_model.ckpt", directory)
            samples = [clip(seed) for seed in range(1, 8)]
            scores = {**{_digest(item): 1.0 for item in samples[:3]},
                      _digest(samples[3]): 0.9, _digest(samples[4]): 0.95,
                      _digest(samples[5]): 0.1, _digest(samples[6]): 0.2}
            authority = ConfirmationAuthority()
            with patch.object(verifier, "_embedding_backend",
                              side_effect=lambda item: vector(scores.get(_digest(item), 1.0))) as backend:
                if enrolled:
                    token = authority.issue(verifier.enrollment_request(samples[:3])).token
                    verifier.enroll(samples[:3], authority=authority, confirmation_token=token)
                if calibrated:
                    request = verifier.calibration_request(samples[3:5], samples[5:7])
                    token = authority.issue(request).token
                    verifier.calibrate(samples[3:5], samples[5:7], authority=authority,
                                       confirmation_token=token)
                yield verifier, authority, samples, scores, backend


def expect_error(call):
    try:
        call()
        assert False, "Expected a closed identity boundary"
    except IdentityError as error:
        assert str(error) == "Owner enrollment or verification is unavailable."


def test_owner_verified_from_fresh_independent_sample():
    with fixture() as (verifier, _, _, _, _):
        recording = clip(10)
        result = verifier.verify(recording)
        assert result.outcome is SpeakerOutcome.OWNER_VERIFIED
        assert result.captured_at == recording.captured_at and result.audio_digest == _digest(recording)
        assert "score" not in repr(result) and result.audio_digest not in repr(result)


def test_unknown_and_uncertain_speakers_never_verified():
    with fixture() as (verifier, _, _, scores, _):
        unknown, uncertain = clip(11), clip(12)
        scores[_digest(unknown)] = -0.3
        scores[_digest(uncertain)] = 0.6
        assert verifier.verify(unknown).outcome is SpeakerOutcome.OWNER_REJECTED
        assert verifier.verify(uncertain).outcome is SpeakerOutcome.OWNER_UNCERTAIN


def test_missing_profile_and_calibration_fail_closed_before_model():
    for enrolled in (False, True):
        with fixture(enrolled=enrolled, calibrated=False) as (verifier, _, _, _, backend):
            backend.reset_mock()
            assert verifier.verify(clip(13)).outcome is SpeakerOutcome.OWNER_UNCERTAIN
            backend.assert_not_called()


def test_invalid_short_silent_constant_and_nonfinite_audio_rejected():
    with fixture() as (verifier, _, _, _, backend):
        cases = [clip(14, seconds=1.5), AudioClip(np.zeros(33600, np.float32)),
                 AudioClip(np.full(33600, 0.1, np.float32)),
                 clip(15, captured_at=time.monotonic() - 31),
                 clip(16, captured_at=time.monotonic() + 10)]
        for value in (float("nan"), float("inf")):
            samples = clip(17).samples.copy()
            samples[0] = value
            cases.append(AudioClip(samples))
        backend.reset_mock()
        for recording in cases:
            assert verifier.verify(recording).outcome is SpeakerOutcome.OWNER_UNCERTAIN
        backend.assert_not_called()


def test_enrollment_requires_three_distinct_samples():
    with fixture(enrolled=False, calibrated=False) as (verifier, _, samples, _, backend):
        expect_error(lambda: verifier.enrollment_request(samples[:2]))
        expect_error(lambda: verifier.enrollment_request([samples[0]] * 3))
        assert not (verifier.profile_store / "enrollment.json").exists()
        backend.assert_not_called()


def test_missing_forged_expired_and_mismatched_tokens_block_enrollment():
    with fixture(enrolled=False, calibrated=False) as (verifier, authority, samples, _, backend):
        for token in (None, "forged", True):
            expect_error(lambda: verifier.enroll(samples[:3], authority=authority, confirmation_token=token))
        request = verifier.enrollment_request(samples[:3])
        token = authority.issue(request).token
        with patch("desktop.confirmation_authority.time.monotonic", return_value=time.monotonic() + 60):
            expect_error(lambda: verifier.enroll(samples[:3], authority=authority, confirmation_token=token))
        token = authority.issue(dict(request, action="calibrate_voice_owner")).token
        expect_error(lambda: verifier.enroll(samples[:3], authority=authority, confirmation_token=token))
        assert not (verifier.profile_store / "enrollment.json").exists()
        backend.assert_not_called()


def test_reused_token_and_replacement_cannot_overwrite_owner():
    with fixture(enrolled=False, calibrated=False) as (verifier, authority, samples, _, backend):
        request = verifier.enrollment_request(samples[:3])
        token = authority.issue(request).token
        verifier.enroll(samples[:3], authority=authority, confirmation_token=token)
        original = (verifier.profile_store / "enrollment.json").read_bytes()
        backend.reset_mock()
        expect_error(lambda: verifier.enroll(samples[:3], authority=authority, confirmation_token=token))
        fresh_token = authority.issue(request).token
        expect_error(lambda: verifier.enroll(samples[:3], authority=authority, confirmation_token=fresh_token))
        assert (verifier.profile_store / "enrollment.json").read_bytes() == original
        backend.assert_not_called()


def test_calibration_requires_separate_owner_nonowner_heldout_samples():
    with fixture(calibrated=False) as (verifier, _, samples, _, _):
        expect_error(lambda: verifier.calibration_request(samples[3:4], samples[5:7]))
        expect_error(lambda: verifier.calibration_request(samples[3:5], samples[5:6]))
        expect_error(lambda: verifier.calibration_request(samples[:2], samples[5:7]))
        expect_error(lambda: verifier.calibration_request(samples[3:5], samples[3:5]))
        assert verifier.verify(clip(18)).outcome is SpeakerOutcome.OWNER_UNCERTAIN


def test_calibration_missing_confirmation_and_changed_sample_blocked():
    with fixture(calibrated=False) as (verifier, authority, samples, _, backend):
        backend.reset_mock()
        expect_error(lambda: verifier.calibrate(samples[3:5], samples[5:7], authority=authority,
                                                confirmation_token="forged"))
        token = authority.issue(verifier.calibration_request(samples[3:5], samples[5:7])).token
        expect_error(lambda: verifier.calibrate(samples[3:5], [samples[5], clip(19)],
                                                authority=authority, confirmation_token=token))
        backend.assert_not_called()
        assert not (verifier.profile_store / "calibration.json").exists()


def test_overlapping_calibration_rejected_without_default_threshold():
    with fixture(calibrated=False) as (verifier, authority, samples, scores, _):
        scores[_digest(samples[6])] = 0.99
        request = verifier.calibration_request(samples[3:5], samples[5:7])
        token = authority.issue(request).token
        expect_error(lambda: verifier.calibrate(samples[3:5], samples[5:7], authority=authority,
                                                confirmation_token=token))
        assert not (verifier.profile_store / "calibration.json").exists()
        assert verifier.verify(clip(20)).outcome is SpeakerOutcome.OWNER_UNCERTAIN


def test_calibration_cutoffs_are_sample_derived_and_immutable():
    with fixture() as (verifier, authority, samples, _, backend):
        path = verifier.profile_store / "calibration.json"
        original = path.read_bytes()
        record = json.loads(original)
        assert record["accept_floor"] == min(record["owner_scores"])
        assert record["reject_ceiling"] == max(record["nonowner_scores"])
        request = verifier.calibration_request(samples[3:5], samples[5:7])
        token = authority.issue(request).token
        backend.reset_mock()
        expect_error(lambda: verifier.calibrate(samples[3:5], samples[5:7], authority=authority,
                                                confirmation_token=token))
        backend.assert_not_called()
        assert path.read_bytes() == original


def test_corrupted_or_changed_profile_and_calibration_fail_closed():
    for name in ("enrollment.json", "calibration.json"):
        with fixture() as (verifier, _, _, _, backend):
            path = verifier.profile_store / name
            original = path.read_bytes()
            for data in (b"not-json", b'{"version":1,"version":1}',
                         json.dumps(dict(json.loads(original), model_id="forged")).encode(),
                         json.dumps(dict(json.loads(original), bypass=True)).encode()):
                path.write_bytes(data)  # Synthetic test artifact only.
                backend.reset_mock()
                assert verifier.verify(clip(21)).outcome is SpeakerOutcome.OWNER_UNCERTAIN
                backend.assert_not_called()


def test_profile_and_calibration_binding_is_exact():
    with fixture() as (verifier, _, _, _, backend):
        path = verifier.profile_store / "enrollment.json"
        profile = json.loads(path.read_bytes())
        profile["centroid"] = vector(0.99)
        path.write_text(json.dumps(profile), encoding="ascii")
        backend.reset_mock()
        assert verifier.verify(clip(22)).outcome is SpeakerOutcome.OWNER_UNCERTAIN
        backend.assert_not_called()


def test_backend_and_storage_errors_do_not_expose_private_values():
    with fixture() as (verifier, _, _, _, backend):
        secret = "synthetic private sample and local path"
        backend.side_effect = RuntimeError(secret)
        result = verifier.verify(clip(23))
        assert result.outcome is SpeakerOutcome.OWNER_UNCERTAIN and secret not in repr(result)
        with patch("voice.identity.private_read", side_effect=RuntimeError(secret)):
            result = verifier.verify(clip(24))
        assert result.outcome is SpeakerOutcome.OWNER_UNCERTAIN and secret not in repr(result)


def test_enrollment_persists_no_raw_audio_or_transcript():
    with fixture() as (verifier, _, samples, _, _):
        assert sorted(path.name for path in verifier.profile_store.iterdir()) == [
            "calibration.json", "enrollment.json"]
        for path in verifier.profile_store.iterdir():
            data = path.read_bytes()
            assert len(data) <= 16384
            assert b"transcript" not in data and b"raw_audio" not in data
            for recording in samples:
                assert recording.samples.tobytes() not in data


def test_playback_similarity_is_not_claimed_to_prove_liveness():
    with fixture() as (verifier, _, samples, _, _):
        # Same waveform replayed with a fresh capture time can still match.
        # Runtime must independently require actual local user confirmation.
        playback = AudioClip(samples[0].samples, captured_at=time.monotonic())
        assert verifier.verify(playback).outcome is SpeakerOutcome.OWNER_VERIFIED


def test_invalid_model_vectors_never_verify():
    with fixture() as (verifier, _, _, _, backend):
        backend.side_effect = None
        for output in ([0.0] * 192, [1.0], [float("nan")] * 192, [float("inf")] * 192):
            backend.return_value = output
            assert verifier.verify(clip(25)).outcome is SpeakerOutcome.OWNER_UNCERTAIN


def test_wrong_model_file_rejected_before_loading_or_network():
    with fixture() as (verifier, _, _, _, _):
        model = verifier.profile_store.parent / "models" / "embedding_model.ckpt"
        model.parent.mkdir()
        model.write_bytes(b"synthetic untrusted model")
        verifier.model_path = model
        # Call the real implementation despite the fixture's synthetic adapter.
        with patch("voice.identity.MODEL_ROOT", model.parent), patch("socket.socket") as socket:
            expect_error(lambda: SpeakerVerifier._embedding_backend(verifier, clip(26)))
            socket.assert_not_called()


def test_warmup_uses_synthetic_audio_without_loading_owner_profile():
    with fixture(enrolled=False, calibrated=False) as (verifier, _, _, _, backend):
        with patch("voice.identity.private_read") as read:
            assert verifier.warmup() is True
        read.assert_not_called()
        assert backend.call_count == 1
        generated = backend.call_args.args[0]
        assert generated.sample_rate == 16000 and generated.samples.shape == (33600,)
        assert generated.samples.flags.writeable is False
        assert list(verifier.profile_store.iterdir()) == []


def test_warmup_failure_is_sanitized_and_close_releases_model_only():
    with fixture() as (verifier, _, _, _, backend):
        before = {path.name: path.read_bytes() for path in verifier.profile_store.iterdir()}
        backend.side_effect = RuntimeError("synthetic private model path")
        expect_error(verifier.warmup)
        verifier._model = object()
        verifier.close()
        assert verifier._model is None
        assert {path.name: path.read_bytes() for path in verifier.profile_store.iterdir()} == before


def test_artifact_types_do_not_accept_boolean_versions_or_thresholds():
    for name, key in (("enrollment.json", "version"), ("calibration.json", "version"),
                      ("calibration.json", "accept_floor"), ("calibration.json", "reject_ceiling")):
        with fixture() as (verifier, _, _, _, backend):
            path = verifier.profile_store / name
            record = json.loads(path.read_bytes())
            record[key] = True
            path.write_text(json.dumps(record), encoding="ascii")
            backend.reset_mock()
            assert verifier.verify(clip(27)).outcome is SpeakerOutcome.OWNER_UNCERTAIN
            backend.assert_not_called()


if __name__ == "__main__":
    tests = [value for name, value in list(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print(f"Voice identity: {len(tests)} passed (synthetic; no physical speakers)")
