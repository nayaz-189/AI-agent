"""A strict adapter for the existing enrolled ECAPA speaker verifier.

The existing calibrated threshold remains authoritative. Conditioning only repairs
low microphone gain; it never changes thresholds or records biometric samples.
"""
from dataclasses import dataclass
import math
import numpy as np
from .endpoint import RATE


class OwnerUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class VoiceCheck:
    status: str
    seconds: float
    input_rms: float
    conditioned_pcm: bytes | None = None

    @property
    def accepted(self):
        return self.status == 'owner_verified'


def condition_pcm(pcm: bytes) -> VoiceCheck:
    """Conservative, amplitude-only conditioning. No AGC on silence/noise.

    Return a reason with no PCM if the old verifier cannot safely evaluate it.
    """
    if not isinstance(pcm, bytes) or len(pcm) % 2 or len(pcm) == 0 or len(pcm) > RATE * 2 * 12:
        return VoiceCheck('bad_audio', 0.0, 0.0)
    x = np.frombuffer(pcm, dtype='<i2').astype(np.float32) / 32768.0
    seconds = float(len(x)) / RATE
    if seconds < 2.0:
        return VoiceCheck('too_short_for_owner_check', seconds, 0.0)
    level = float(np.sqrt(np.mean(x * x)))
    peak = float(np.max(np.abs(x)))
    dc = float(abs(np.mean(x)))
    if not math.isfinite(level) or not math.isfinite(peak):
        return VoiceCheck('bad_audio', seconds, 0.0)
    if level < 0.0006 or peak < 0.002:
        return VoiceCheck('microphone_signal_too_low', seconds, round(level, 6))
    if peak >= 0.999 or dc > max(0.01, level * 0.60):
        return VoiceCheck('distorted_audio', seconds, round(level, 6))
    if level > 0.6:
        return VoiceCheck('distorted_audio', seconds, round(level, 6))
    gain = min(12.0, max(1.0, 0.024 / max(level, 1e-8)), 0.97 / peak)
    y = x * gain
    if float(np.sqrt(np.mean(y * y))) < 0.0052:
        return VoiceCheck('microphone_signal_too_low', seconds, round(level, 6))
    # No clipping and no inversion of signal. Speaker matching still happens below.
    output = np.rint(np.clip(y, -0.98, 0.98) * 32767).astype('<i2').tobytes()
    return VoiceCheck('ready_for_owner_check', seconds, round(level, 6), output)


class ExistingOwnerGate:
    def __init__(self):
        from pathlib import Path
        from voice.identity import SpeakerVerifier, IDENTITY_ROOT, MODEL_ROOT
        root = Path(IDENTITY_ROOT)
        if not all((root / n).is_file() for n in ('enrollment.json', 'calibration.json')):
            raise OwnerUnavailable('Owner profile/calibration missing. Do not bypass enrollment.')
        self.verifier = SpeakerVerifier(MODEL_ROOT / 'ecapa' / 'embedding_model.ckpt')
        # Multi-style enrollment is optional. A malformed ACTIVE profile fails
        # closed, never back to a weaker profile or to an unverified action.
        from .multistyle import active
        self.multistyle = active()

    def check(self, pcm: bytes) -> VoiceCheck:
        prepared = condition_pcm(pcm)
        if prepared.conditioned_pcm is None:
            return prepared
        from voice.audio import AudioClip
        from voice.identity import SpeakerOutcome
        x = np.frombuffer(prepared.conditioned_pcm, dtype='<i2').astype(np.float32) / 32768.0
        # New multi-style profile is an independently validated alternative to
        # the historical single-centroid profile, not an unrestricted override.
        if self.multistyle is not None:
            try:
                from .multistyle import classify_embedding
                vector = self.verifier.embed(AudioClip(x, sample_rate=RATE))
                status, _score = classify_embedding(vector, self.multistyle)
                return VoiceCheck(status, prepared.seconds, prepared.input_rms,
                                  prepared.conditioned_pcm if status == 'owner_verified' else None)
            except Exception:
                return VoiceCheck('verification_uncertain', prepared.seconds, prepared.input_rms)
        # Legacy verifier independently validates freshness, threshold and calibration.
        try:
            verdict = self.verifier.verify(AudioClip(x, sample_rate=RATE))
        except Exception:
            return VoiceCheck('verification_error', prepared.seconds, prepared.input_rms)
        if verdict.outcome is SpeakerOutcome.OWNER_VERIFIED:
            return VoiceCheck('owner_verified', prepared.seconds, prepared.input_rms, prepared.conditioned_pcm)
        if verdict.outcome is SpeakerOutcome.OWNER_REJECTED:
            return VoiceCheck('speaker_mismatch', prepared.seconds, prepared.input_rms)
        return VoiceCheck('verification_uncertain', prepared.seconds, prepared.input_rms)

    def verify(self, pcm: bytes) -> bool:
        """Backward-compatible truth value; no trust session or threshold bypass."""
        return self.check(pcm).accepted
