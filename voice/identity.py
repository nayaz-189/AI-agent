"""Experimental local speaker similarity; never a replacement for permission.

Only the reviewed ECAPA architecture and hash-pinned tensor weights are loaded.
No HyperPyYAML, custom model code, downloads or microphone access occurs here.
Playback and synthesized voices can resemble the owner: every voice action must
also pass the trusted local confirmation boundary and existing execution gates.
"""
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time

from desktop.confirmation_authority import ConfirmationAuthority
from execution.device_storage import private_create, private_directory, private_read


RUNTIME_ROOT = Path(__file__).resolve().parents[1] / "runtime" / "voice"
IDENTITY_ROOT = RUNTIME_ROOT / "identity"
MODEL_ROOT = RUNTIME_ROOT / "models"
ECAPA_REVISION = "1e47a43813bfa3dfebda84fca9620394f74cc55a"
ECAPA_SHA256 = "0575cb64845e6b9a10db9bcb74d5ac32b326b8dc90352671d345e2ee3d0126a2"
MODEL_ID = "ecapa-fbank80-sentence-mean-v1:" + ECAPA_SHA256
DIMENSION = 192


class IdentityError(RuntimeError):
    def __init__(self):
        super().__init__("Owner enrollment or verification is unavailable.")


class SpeakerOutcome(str, Enum):
    OWNER_VERIFIED = "OWNER_VERIFIED"
    OWNER_REJECTED = "OWNER_REJECTED"
    OWNER_UNCERTAIN = "OWNER_UNCERTAIN"


@dataclass(frozen=True)
class Verification:
    outcome: SpeakerOutcome
    captured_at: float
    audio_digest: str = field(repr=False)
    score: float | None = field(default=None, repr=False)


def _number(value):
    return type(value) in {int, float} and math.isfinite(value)


def _unit(vector):
    if (type(vector) not in {list, tuple} or len(vector) != DIMENSION
            or any(not _number(value) for value in vector)):
        raise IdentityError()
    norm = math.sqrt(sum(value * value for value in vector))
    if not math.isfinite(norm) or norm <= 1e-12:
        raise IdentityError()
    return [value / norm for value in vector]


def _cosine(left, right):
    return max(-1.0, min(1.0, sum(a * b for a, b in zip(left, right))))


def _digest(clip):
    return hashlib.sha256(clip.samples.astype("<f4", copy=False).tobytes()).hexdigest()


def _clip(clip, *, max_age):
    # Lazy import keeps missing optional audio packages from breaking text mode.
    from voice.audio import AudioClip, validate_audio
    if type(clip) is not AudioClip:
        raise IdentityError()
    if (not _number(clip.captured_at) or not 0 <= time.monotonic() - clip.captured_at <= max_age):
        raise IdentityError()
    samples = clip.samples.copy()
    samples.flags.writeable = False
    clip = validate_audio(AudioClip(samples=samples, sample_rate=clip.sample_rate,
                                    captured_at=clip.captured_at))
    if clip.sample_rate != 16000 or len(clip.samples) < 32000:
        raise IdentityError()
    return clip


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def _decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise IdentityError()
            result[key] = value
        return result
    return json.loads(raw.decode("ascii"), object_pairs_hook=pairs)


class SpeakerVerifier:
    """Trusted local adapter, with no caller-supplied verdict or threshold.

    Storage is provisioned by the explicit CLI setup flow using private_directory.
    Enrollment and calibration are independent exclusive creations, so enrollment
    can be completed before a consenting non-owner is available for calibration.
    Missing calibration always prevents OWNER_VERIFIED.
    """

    def __init__(self, model_path, profile_store=IDENTITY_ROOT):
        self.model_path = Path(model_path).absolute()
        self.profile_store = Path(profile_store).absolute()
        if self.profile_store != IDENTITY_ROOT.absolute():
            raise IdentityError()
        self._model = None

    def _embedding_backend(self, clip):
        if self._model is None:
            path = self.model_path
            if (not path.is_relative_to(MODEL_ROOT.absolute()) or ".." in path.parts
                    or path.name != "embedding_model.ckpt"):
                raise IdentityError()
            for parent in path.parents:
                info = parent.lstat()
                if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                    raise IdentityError()
            info = path.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or getattr(info, "st_file_attributes", 0) & 0x400
                    or not 1 <= info.st_size <= 100_000_000):
                raise IdentityError()
            # Verify and deserialize the same open handle, without unsafe pickle.
            with path.open("rb") as source:
                opened = os.fstat(source.fileno())
                if (info.st_dev, info.st_ino) != (opened.st_dev, opened.st_ino):
                    raise IdentityError()
                digest = hashlib.sha256()
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
                if digest.hexdigest() != ECAPA_SHA256:
                    raise IdentityError()
                import torch
                from speechbrain.lobes.features import Fbank
                from speechbrain.processing.features import InputNormalization
                from speechbrain.lobes.models.ECAPA_TDNN import ECAPA_TDNN
                torch.set_num_threads(2)
                source.seek(0)
                weights = torch.load(source, map_location="cpu", weights_only=True)
            model = ECAPA_TDNN(input_size=80, channels=[1024, 1024, 1024, 1024, 3072],
                               kernel_sizes=[5, 3, 3, 3, 1], dilations=[1, 2, 3, 4, 1],
                               attention_channels=128, lin_neurons=DIMENSION)
            model.load_state_dict(weights, strict=True)
            self._model = (torch, Fbank(n_mels=80).eval(),
                           InputNormalization(norm_type="sentence", std_norm=False).eval(), model.eval())
        torch, features, normalize, model = self._model
        with torch.inference_mode():
            waveform = torch.from_numpy(clip.samples.copy()).unsqueeze(0)
            lengths = torch.ones(1)
            output = model(normalize(features(waveform), lengths), lengths)
            return output.reshape(-1).tolist()

    def warmup(self):
        """Load local weights before capture, using only a synthetic sine wave.

        This proves model execution is available, not speaker accuracy or owner
        enrollment. No profile, microphone, recorded audio or network is used.
        """
        try:
            import numpy as np
            from voice.audio import AudioClip
            samples = (0.1 * np.sin(np.arange(33600, dtype=np.float32) * 0.07)).astype(np.float32)
            self.embed(AudioClip(samples, captured_at=time.monotonic()))
            return True
        except Exception:
            raise IdentityError() from None

    def close(self):
        """Release this adapter's model references; no stored identity changes."""
        self._model = None

    def embed(self, clip):
        """Return a private embedding, not an authorization credential."""
        try:
            return _unit(self._embedding_backend(_clip(clip, max_age=900)))
        except Exception:
            raise IdentityError() from None

    def _samples(self, clips, minimum):
        if type(clips) not in {list, tuple} or not minimum <= len(clips) <= 8:
            raise IdentityError()
        copies = [_clip(clip, max_age=900) for clip in clips]
        digests = [_digest(clip) for clip in copies]
        if len(set(digests)) != len(digests):
            raise IdentityError()
        return copies, digests

    def enrollment_request(self, clips):
        """Exact non-audio proposal for the real local permission interface."""
        try:
            _, digests = self._samples(clips, 3)
            return {"action": "enroll_voice_owner", "model_id": MODEL_ID,
                    "sample_digests": digests, "storage": "private_local_owner_profile",
                    "experimental": True}
        except Exception:
            raise IdentityError() from None

    @staticmethod
    def _authorize(request, authority, token):
        if (type(authority) is not ConfirmationAuthority
                or authority.consume(token, request).get("confirmed") is not True):
            raise IdentityError()

    def enroll(self, clips, *, authority, confirmation_token):
        try:
            clips, digests = self._samples(clips, 3)
            request = self.enrollment_request(clips)
            self._authorize(request, authority, confirmation_token)
            directory = private_directory(self.profile_store)
            # Refuse replacement before expensive model work; exclusive create
            # below is the final race-safe check against another enrollment.
            if (directory / "enrollment.json").exists() or (directory / "calibration.json").exists():
                raise IdentityError()
            vectors = [self.embed(clip) for clip in clips]
            centroid = _unit([sum(column) / len(vectors) for column in zip(*vectors)])
            profile = {"version": 1, "model_id": MODEL_ID, "centroid": centroid,
                       "sample_digests": digests, "sample_count": len(clips)}
            private_create(directory, "enrollment.json", _encode(profile))
        except Exception:
            raise IdentityError() from None

    def _profile(self):
        raw = private_read(self.profile_store, "enrollment.json")
        profile = _decode(raw)
        if (type(profile) is not dict or set(profile) != {
                "version", "model_id", "centroid", "sample_digests", "sample_count"}
                or type(profile["version"]) is not int or profile["version"] != 1
                or profile["model_id"] != MODEL_ID
                or type(profile["sample_count"]) is not int or not 3 <= profile["sample_count"] <= 8
                or type(profile["sample_digests"]) is not list
                or len(profile["sample_digests"]) != profile["sample_count"]
                or any(type(item) is not str or len(item) != 64
                       or any(c not in "0123456789abcdef" for c in item) for item in profile["sample_digests"])
                or len(set(profile["sample_digests"])) != profile["sample_count"]):
            raise IdentityError()
        centroid = _unit(profile["centroid"])
        if any(abs(a - b) > 1e-8 for a, b in zip(centroid, profile["centroid"])):
            raise IdentityError()
        return profile, hashlib.sha256(raw).hexdigest()

    def calibration_request(self, owner_checks, nonowner_checks):
        try:
            profile, binding = self._profile()
            _, owners = self._samples(owner_checks, 2)
            _, others = self._samples(nonowner_checks, 2)
            all_digests = profile["sample_digests"] + owners + others
            if len(set(all_digests)) != len(all_digests):
                raise IdentityError()
            return {"action": "calibrate_voice_owner", "profile_digest": binding,
                    "owner_sample_digests": owners, "nonowner_sample_digests": others,
                    "experimental": True}
        except Exception:
            raise IdentityError() from None

    def calibrate(self, owner_checks, nonowner_checks, *, authority, confirmation_token):
        try:
            owner_checks, _ = self._samples(owner_checks, 2)
            nonowner_checks, _ = self._samples(nonowner_checks, 2)
            request = self.calibration_request(owner_checks, nonowner_checks)
            self._authorize(request, authority, confirmation_token)
            if (self.profile_store / "calibration.json").exists():
                raise IdentityError()
            profile, binding = self._profile()
            if binding != request["profile_digest"]:
                raise IdentityError()
            centroid = profile["centroid"]
            owners = [_cosine(self.embed(clip), centroid) for clip in owner_checks]
            others = [_cosine(self.embed(clip), centroid) for clip in nonowner_checks]
            # Empirical guard band, not a universal or statistically validated
            # false-accept threshold. Overlap means voice actions remain blocked.
            if min(owners) - max(others) <= 1e-6:
                raise IdentityError()
            record = {"version": 1, "model_id": MODEL_ID, "profile_digest": binding,
                      "owner_scores": owners, "nonowner_scores": others,
                      "accept_floor": min(owners), "reject_ceiling": max(others)}
            private_create(self.profile_store, "calibration.json", _encode(record))
        except Exception:
            raise IdentityError() from None

    def _calibration(self, binding):
        record = _decode(private_read(self.profile_store, "calibration.json"))
        if (type(record) is not dict or set(record) != {"version", "model_id", "profile_digest",
                "owner_scores", "nonowner_scores", "accept_floor", "reject_ceiling"}
                or type(record["version"]) is not int or record["version"] != 1
                or record["model_id"] != MODEL_ID
                or record["profile_digest"] != binding):
            raise IdentityError()
        for name in ("owner_scores", "nonowner_scores"):
            scores = record[name]
            if (type(scores) is not list or not 2 <= len(scores) <= 8
                    or any(not _number(value) or not -1 <= value <= 1 for value in scores)):
                raise IdentityError()
        if (not _number(record["accept_floor"]) or not _number(record["reject_ceiling"])
                or record["accept_floor"] != min(record["owner_scores"])
                or record["reject_ceiling"] != max(record["nonowner_scores"])
                or record["accept_floor"] - record["reject_ceiling"] <= 1e-6):
            raise IdentityError()
        return record

    def verify(self, clip):
        """Verify this recording only; session state cannot grant owner identity."""
        captured_at, digest = 0.0, ""
        try:
            clip = _clip(clip, max_age=30)
            captured_at, digest = clip.captured_at, _digest(clip)
            profile, binding = self._profile()
            calibration = self._calibration(binding)
            score = _cosine(self.embed(clip), profile["centroid"])
            # Model loading/inference must not silently extend freshness.
            _clip(clip, max_age=30)
            outcome = SpeakerOutcome.OWNER_UNCERTAIN
            if score >= calibration["accept_floor"]:
                outcome = SpeakerOutcome.OWNER_VERIFIED
            elif score <= calibration["reject_ceiling"]:
                outcome = SpeakerOutcome.OWNER_REJECTED
            return Verification(outcome, captured_at, digest, score)
        except Exception:
            return Verification(SpeakerOutcome.OWNER_UNCERTAIN, captured_at, digest)
