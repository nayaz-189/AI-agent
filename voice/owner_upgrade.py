"""Version-two owner enrollment overlay; original Day 18 owner files are immutable.

15 explicitly captured new owner clips contribute to a new centroid alongside the
existing enrolled centroid. No raw audio or embeddings persist: only the aggregate
centroid and hashes. A new, separately authorized calibration is mandatory.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from execution.device_storage import private_create, private_read
from voice.identity import (
    DIMENSION, MODEL_ID, IdentityError, SpeakerVerifier,
    _clip, _cosine, _decode, _digest, _encode, _number, _unit,
)

PROFILE_V2 = "enrollment-v2.json"
CALIBRATION_V2 = "calibration-v2.json"
SAMPLE_COUNT = 15

PROMPTS = (
    ("Neutral", "Hey Vorak, today I'm checking whether you recognize my everyday speaking voice."),
    ("Casual", "Yo Vorak, what's good, dawg? I've got some work for us to finish tonight."),
    ("Professional", "Please review this project carefully and summarize the most important technical issues."),
    ("Slow", "I'm speaking slowly and clearly because voice recognition matters to this project."),
    ("Fast", "Alright Vorak, we've got three things to finish, so let's get moving right now."),
    ("Curious", "Why do you sometimes have trouble recognizing my voice when I'm clearly talking to you?"),
    ("Serious", "Before taking any action, verify the request and follow the computer's security policies."),
    ("Relaxed", "I was thinking about our project earlier, and it's actually coming together quite nicely."),
    ("Excited", "Holy shit Vorak, we finally got the voice engine working properly on this laptop!"),
    ("Soft", "I'm speaking a little more softly now, but my words should still be very clear."),
    ("Firm", "Listen up Vorak, I need you to pay attention to what I'm telling you right now."),
    ("Questioning", "Can you tell me whether you understand this sentence and recognize who is talking?"),
    ("Lower pitch", "This time I'm using a lower, steadier tone while speaking in a natural way."),
    ("Animated", "That's actually amazing! I didn't expect the entire thing to work this well today!"),
    ("Command style", "Yo Vorak, pull up Calculator. I have a few numbers to check for our project."),
)


def _exists(path):
    """Treat symlinks (including broken ones) as present, not a downgrade signal."""
    return path.exists() or path.is_symlink()


class UpgradedSpeakerVerifier(SpeakerVerifier):
    def _legacy_profile(self):
        return super()._profile()

    def _profile(self):
        legacy, legacy_digest = self._legacy_profile()
        path = self.profile_store / PROFILE_V2
        if not _exists(path):
            # Never silently downgrade when a v2 calibration is unexpectedly present.
            if _exists(self.profile_store / CALIBRATION_V2):
                raise IdentityError()
            return legacy, legacy_digest
        raw = private_read(self.profile_store, PROFILE_V2)
        profile = _decode(raw)
        if (type(profile) is not dict or set(profile) != {
                "version", "model_id", "legacy_profile_digest", "centroid",
                "sample_digests", "sample_count", "legacy_sample_count"}
                or type(profile["version"]) is not int or profile["version"] != 2
                or profile["model_id"] != MODEL_ID
                or profile["legacy_profile_digest"] != legacy_digest
                or type(profile["sample_count"]) is not int
                or profile["sample_count"] != SAMPLE_COUNT
                or type(profile["legacy_sample_count"]) is not int
                or profile["legacy_sample_count"] != legacy["sample_count"]
                or type(profile["sample_digests"]) is not list
                or len(profile["sample_digests"]) != SAMPLE_COUNT
                or any(type(item) is not str or len(item) != 64
                       or any(c not in "0123456789abcdef" for c in item)
                       for item in profile["sample_digests"])
                or len(set(profile["sample_digests"])) != SAMPLE_COUNT
                or set(profile["sample_digests"]) & set(legacy["sample_digests"])):
            raise IdentityError()
        centroid = _unit(profile["centroid"])
        if any(abs(a - b) > 1e-8 for a, b in zip(centroid, profile["centroid"])):
            raise IdentityError()
        return profile, hashlib.sha256(raw).hexdigest()

    def _calibration(self, binding):
        profile, digest = self._profile()
        if digest != binding:
            raise IdentityError()
        if profile["version"] == 1:
            return super()._calibration(binding)
        record = _decode(private_read(self.profile_store, CALIBRATION_V2))
        if (type(record) is not dict or set(record) != {
                "version", "model_id", "profile_digest", "owner_scores",
                "nonowner_scores", "accept_floor", "reject_ceiling"}
                or type(record["version"]) is not int or record["version"] != 2
                or record["model_id"] != MODEL_ID
                or record["profile_digest"] != binding):
            raise IdentityError()
        for name in ("owner_scores", "nonowner_scores"):
            scores = record[name]
            if (type(scores) is not list or not 2 <= len(scores) <= 8
                    or any(not _number(score) or not -1 <= score <= 1 for score in scores)):
                raise IdentityError()
        if (not _number(record["accept_floor"]) or not _number(record["reject_ceiling"])
                or record["accept_floor"] != min(record["owner_scores"])
                or record["reject_ceiling"] != max(record["nonowner_scores"])
                or record["accept_floor"] <= record["reject_ceiling"]):
            raise IdentityError()
        return record

    def calibrate(self, owner_checks, nonowner_checks, *, authority, confirmation_token):
        profile, binding = self._profile()
        if profile["version"] == 1:
            return super().calibrate(owner_checks, nonowner_checks,
                                     authority=authority, confirmation_token=confirmation_token)
        try:
            owner_checks, _ = self._samples(owner_checks, 2)
            nonowner_checks, _ = self._samples(nonowner_checks, 2)
            request = self.calibration_request(owner_checks, nonowner_checks)
            self._authorize(request, authority, confirmation_token)
            if _exists(self.profile_store / CALIBRATION_V2):
                raise IdentityError()
            current, current_binding = self._profile()
            if current_binding != binding or current["version"] != 2:
                raise IdentityError()
            owners = [_cosine(self.embed(clip), profile["centroid"]) for clip in owner_checks]
            others = [_cosine(self.embed(clip), profile["centroid"]) for clip in nonowner_checks]
            if min(owners) - max(others) <= 1e-6:
                raise IdentityError()
            record = {"version": 2, "model_id": MODEL_ID, "profile_digest": binding,
                      "owner_scores": owners, "nonowner_scores": others,
                      "accept_floor": min(owners), "reject_ceiling": max(others)}
            private_create(self.profile_store, CALIBRATION_V2, _encode(record))
        except Exception:
            raise IdentityError() from None


class OwnerUpgradeSession:
    """Memory-only collection. Does not alter any files until explicit approval."""

    def __init__(self, verifier):
        if type(verifier) is not UpgradedSpeakerVerifier:
            raise IdentityError()
        self.verifier = verifier
        legacy, binding = verifier._legacy_profile()
        verifier._calibration(binding)  # Existing enrolled profile must be valid.
        if _exists(verifier.profile_store / PROFILE_V2) or _exists(verifier.profile_store / CALIBRATION_V2):
            raise IdentityError()
        self.legacy = legacy
        self.binding = binding
        self.vectors = []
        self.digests = []
        self._committed = False

    def add(self, clip):
        if self._committed or len(self.vectors) >= SAMPLE_COUNT:
            raise IdentityError()
        checked = _clip(clip, max_age=30)
        import numpy as np
        frames = checked.samples.reshape(-1, 1600)
        rms = np.sqrt(np.mean(frames ** 2, axis=1))
        noise = float(np.percentile(rms, 20))
        # Energy gate only; not a true VAD or anti-spoof system.
        active_seconds = float(np.count_nonzero(rms > max(0.012, min(0.03, noise * 1.8)))) / 10
        if active_seconds < 2.0:
            raise ValueError("Too little active audio. Please repeat the current sentence.")
        digest = _digest(checked)
        if digest in self.digests or digest in self.legacy["sample_digests"]:
            raise IdentityError()
        vector = self.verifier.embed(checked)
        self.vectors.append(vector)
        self.digests.append(digest)
        return round(active_seconds, 1)

    def proposal(self):
        if self._committed or len(self.vectors) != SAMPLE_COUNT or len(self.digests) != SAMPLE_COUNT:
            raise IdentityError()
        return {"action": "upgrade_voice_owner", "model_id": MODEL_ID,
                "legacy_profile_digest": self.binding,
                "sample_digests": list(self.digests), "sample_count": SAMPLE_COUNT,
                "storage": "private_local_owner_profile_v2", "experimental": True}

    def commit(self, *, authority, confirmation_token):
        request = self.proposal()
        try:
            self.verifier._authorize(request, authority, confirmation_token)
            legacy, binding = self.verifier._legacy_profile()
            if binding != self.binding or _exists(self.verifier.profile_store / PROFILE_V2):
                raise IdentityError()
            if _exists(self.verifier.profile_store / CALIBRATION_V2):
                raise IdentityError()
            count = legacy["sample_count"]
            summed = [
                (count * legacy["centroid"][i] + sum(v[i] for v in self.vectors)) / (count + SAMPLE_COUNT)
                for i in range(DIMENSION)
            ]
            centroid = _unit(summed)
            record = {"version": 2, "model_id": MODEL_ID,
                      "legacy_profile_digest": binding, "centroid": centroid,
                      "sample_digests": list(self.digests), "sample_count": SAMPLE_COUNT,
                      "legacy_sample_count": count}
            private_create(self.verifier.profile_store, PROFILE_V2, _encode(record))
            self._committed = True
            self.vectors.clear()
            self.digests.clear()
        except Exception:
            raise IdentityError() from None
