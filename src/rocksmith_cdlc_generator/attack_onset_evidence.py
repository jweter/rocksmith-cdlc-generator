"""Per-event attack evidence from PCM energy, independent of F0/pYIN.

An onset detector's normalized spectral peak is not independent evidence that
audio energy actually rose at the chosen event boundary. This conservative
negative/control measurement examines only 20-ms time-domain RMS windows
around five positions after a backtracked onset boundary. It never receives a
MIDI pitch, f0, pitch confidence, model or external file path and never
grants instrument/musical trust.

A sustained tonal signal, unrelated sound or drum can all be energetic; this
measurement proves only *local amplitude change*, not a Bass instrument.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

WINDOW_SECONDS = 0.020
SEARCH_STEP_SECONDS = 0.010
SEARCH_COUNT = 9
MIN_POST_RMS = 0.008


@dataclass(frozen=True)
class AttackOnsetEvidence:
    status: str
    confidence: float
    examined_positions: int
    fundamental_pitch_used: bool = False
    bass_instrument_verified: bool = False
    musical_pass_proven: bool = False

    @property
    def corroborated(self) -> bool:
        return self.status == "observed_attack"


def _rms(samples: Sequence[float], first: int, end: int) -> float:
    if first < 0 or end > len(samples) or first >= end:
        raise ValueError("INVALID_ATTACK_EVIDENCE_WINDOW")
    # AC RMS rejects a constant/DC offset masquerading as an attack.
    count = end - first
    total = 0.0
    square = 0.0
    for index in range(first, end):
        value = float(samples[index])
        if not math.isfinite(value):
            raise ValueError("INVALID_ATTACK_EVIDENCE_SAMPLE")
        total += value
        square += value * value
    mean = total / count
    return math.sqrt(max(0.0, square / count - mean * mean))


def inspect_attack_onset(
    samples: Sequence[float], sample_rate: int, boundary_seconds: float,
) -> AttackOnsetEvidence:
    """Measure best time-domain energy rise near the *detected* onset boundary.

    This does not read a pitch estimate, score, or filename. An initial
    chunk boundary or insufficient pre-onset audio returns no evidence.
    Every positive value requires pre- AND post-onset PCM observations.
    """
    if (type(sample_rate) is not int or not 8000 <= sample_rate <= 192000
            or type(boundary_seconds) not in (int, float)
            or not math.isfinite(boundary_seconds) or boundary_seconds < 0):
        raise ValueError("INVALID_ATTACK_EVIDENCE_GEOMETRY")
    width = round(WINDOW_SECONDS * sample_rate)
    step = round(SEARCH_STEP_SECONDS * sample_rate)
    boundary = round(boundary_seconds * sample_rate)
    count = 0
    best = 0.0
    try:
        for offset in range(SEARCH_COUNT):
            midpoint = boundary + offset * step
            first, end = midpoint - width, midpoint + width
            if first < 0 or end > len(samples):
                continue
            prior = _rms(samples, first, midpoint)
            after = _rms(samples, midpoint, end)
            count += 1
            if after < MIN_POST_RMS:
                continue
            increase = max(0.0, (after - prior) / max(after, MIN_POST_RMS))
            best = max(best, min(1.0, increase))
    except (ValueError, TypeError, OverflowError, IndexError):
        return AttackOnsetEvidence("unavailable", 0.0, count)
    if not count:
        return AttackOnsetEvidence("unavailable", 0.0, 0)
    if best <= 0.0:
        return AttackOnsetEvidence("no_attack", 0.0, count)
    return AttackOnsetEvidence("observed_attack", round(best, 6), count)
