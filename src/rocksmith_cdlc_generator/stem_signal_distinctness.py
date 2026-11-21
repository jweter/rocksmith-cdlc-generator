"""Conservative audio-signal clone screen for Bass evidence trust.

This proves only that two PCM recordings are not merely the same samples
with a gain/phase/DC transformation. It does NOT prove that a changed signal
is a genuinely isolated Bass instrument. Used only as an extra fail-closed
necessary condition for future per-note trust promotion.
"""
from __future__ import annotations

from array import array
from dataclasses import dataclass
from math import isfinite, sqrt
from pathlib import Path
import sys
import wave

from .hashing import sha256_file


@dataclass(frozen=True)
class StemDifferenceScreen:
    status: str  # nontrivial_difference, indistinguishable, ambiguous, incompatible
    evaluated_windows: int
    distinct_windows: int
    reason: str


def _read_window(path: Path, begin: int, count: int, channels: int) -> array:
    with wave.open(str(path), "rb") as source:
        source.setpos(begin)
        data = source.readframes(count)
    if len(data) != count * channels * 2:
        raise ValueError("Truncated PCM input")
    samples = array("h")
    samples.frombytes(data)
    if sys.byteorder != "little":
        samples.byteswap()
    return samples


def _absolute_correlation(a: array, b: array) -> float | None:
    if len(a) != len(b) or not a:
        return None
    n = len(a)
    mean_a, mean_b = sum(a) / n, sum(b) / n
    va, vb, xy = 0.0, 0.0, 0.0
    for x, y in zip(a, b):
        dx = x - mean_a
        dy = y - mean_b
        va += dx * dx
        vb += dy * dy
        xy += dx * dy
    # No meaningful pitch/signal evidence in near-constant or quiet PCM.
    if va / n < 60 * 60 or vb / n < 60 * 60:
        return None
    result = abs(xy / sqrt(va * vb))
    return min(1.0, result) if isfinite(result) else None


def screen_stem_nontrivial_difference(
    source_path: Path, stem_path: Path, *,
    window_seconds: float = 0.4,
    max_windows: int = 12,
    minimum_distinct_windows: int = 2,
) -> StemDifferenceScreen:
    """Reject exact and gain/phase-scaled full-mix clones as note authority.

    Multiple independent signal-bearing windows must have substantial
    nonproportional sample content. A weak or silent case stays ambiguous.
    The output is *not* a source separation purity verdict.
    """
    if not 0.2 <= window_seconds <= 1.0 or not 4 <= max_windows <= 16:
        raise ValueError("Invalid bounded signal-screen parameters")
    if not 2 <= minimum_distinct_windows <= max_windows:
        raise ValueError("Invalid independent window requirement")
    source_path, stem_path = Path(source_path), Path(stem_path)
    try:
        with wave.open(str(source_path), "rb") as source:
            params = (
                source.getframerate(), source.getnchannels(),
                source.getnframes(), source.getsampwidth(), source.getcomptype(),
            )
        with wave.open(str(stem_path), "rb") as stem:
            compared = (
                stem.getframerate(), stem.getnchannels(),
                stem.getnframes(), stem.getsampwidth(), stem.getcomptype(),
            )
        if (params != compared or params[0] <= 0 or params[1] not in (1, 2)
                or params[3] != 2 or params[4] != "NONE"):
            return StemDifferenceScreen("incompatible", 0, 0, "PCM geometry differs")
        if sha256_file(source_path) == sha256_file(stem_path):
            return StemDifferenceScreen("indistinguishable", 0, 0,
                                        "Exact full-mix byte clone cannot verify Bass isolation")
        rate, channels, frames, _width, _compression = params
        window = round(rate * window_seconds)
        if window < 100 or frames < 2 * window:
            return StemDifferenceScreen("ambiguous", 0, 0,
                                        "Insufficient independent samples")
        positions = []
        for i in range(max_windows):
            position = round(i * (frames - window) / (max_windows - 1))
            if not positions or position - positions[-1] >= window:
                positions.append(position)
        distinct, evaluated = 0, 0
        for start in positions:
            reference = _read_window(source_path, start, window, channels)
            candidate = _read_window(stem_path, start, window, channels)
            correlation = _absolute_correlation(reference, candidate)
            if correlation is None:
                continue
            evaluated += 1
            # Equivalent to >=3% signal energy unexplained by a single
            # gain/phase/DC transform. This is just a clone detector, not a
            # model of the Bass stem's isolation purity.
            if 1.0 - correlation * correlation >= .03 * .03:
                distinct += 1
        if distinct >= minimum_distinct_windows:
            return StemDifferenceScreen("nontrivial_difference", evaluated, distinct,
                                        "At least two disjoint active windows differ")
        if evaluated < minimum_distinct_windows:
            return StemDifferenceScreen("ambiguous", evaluated, distinct,
                                        "Insufficient active independent windows")
        return StemDifferenceScreen("indistinguishable" if distinct == 0 else "ambiguous",
                                    evaluated, distinct,
                                    "Unable to rule out a gain/phase-scaled full-mix copy")
    except (OSError, ValueError, wave.Error, EOFError):
        return StemDifferenceScreen("incompatible", 0, 0, "Unreadable or truncated PCM")
