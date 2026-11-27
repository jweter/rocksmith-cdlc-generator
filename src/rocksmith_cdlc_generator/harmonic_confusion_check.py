"""Detect octave and harmonic mix-ups between expected and detected pitch (#796 slice 39).

Pitch trackers on distorted guitar often lock onto an overtone: the detected frequency is
an octave (x2, x4, x8) or another harmonic (x3, x5, x6, x7) of the real note, or a
sub-harmonic of it. Comparing detected pitch to the exact score pitch exposes this. This is
a pure check over two frequencies in Hz; invalid input returns ``INVALID_INPUT`` with a
named reason (it never raises and never reports ``MATCH`` for input it could not validate).

``tolerance_cents`` (default 50, at most 100) is how far the detected pitch may sit from an
exact ratio and still be classified. The nearest candidate ratio wins; because the closest
distinct candidates (x7 and x8) are 231 cents apart, a tolerance of at most 100 cents can
never be ambiguous.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict

DEFAULT_TOLERANCE_CENTS = 50.0
MAX_TOLERANCE_CENTS = 100.0
MAX_HARMONIC = 8

HarmonicStatus = Literal[
    "MATCH", "OCTAVE_ERROR", "HARMONIC_ERROR", "MISMATCH", "INVALID_INPUT"
]
Direction = Literal["up", "down", "none"]

_OCTAVE_FACTORS = frozenset({2, 4, 8})


class HarmonicResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: HarmonicStatus
    reason: str = ""
    ratio: float | None = None
    cents_error: float | None = None
    harmonic_number: int | None = None
    direction: Direction = "none"


class HarmonicSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["CLEAR", "CONFUSION_FOUND", "INVALID_INPUT"]
    reason: str = ""
    total: int = 0
    matches: int = 0
    octave_errors: int = 0
    harmonic_errors: int = 0
    mismatches: int = 0
    confusion_rate: float = 0.0


def _is_positive(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
        and value > 0
    )


def _invalid(reason: str) -> HarmonicResult:
    return HarmonicResult(status="INVALID_INPUT", reason=reason)


def classify_harmonic_confusion(
    expected_hz: object,
    detected_hz: object,
    tolerance_cents: object = DEFAULT_TOLERANCE_CENTS,
) -> HarmonicResult:
    """Classify ``detected_hz`` against the exact ``expected_hz`` of the score."""
    if not _is_positive(expected_hz):
        return _invalid("EXPECTED_NOT_POSITIVE_NUMBER")
    if not _is_positive(detected_hz):
        return _invalid("DETECTED_NOT_POSITIVE_NUMBER")
    if not _is_positive(tolerance_cents) or float(tolerance_cents) > MAX_TOLERANCE_CENTS:  # type: ignore[arg-type]
        return _invalid("TOLERANCE_OUT_OF_RANGE")
    tolerance = float(tolerance_cents)  # type: ignore[arg-type]
    ratio = float(detected_hz) / float(expected_hz)  # type: ignore[arg-type]

    best: tuple[float, int, Direction] | None = None
    for n in range(1, MAX_HARMONIC + 1):
        for direction, scale in (("up", float(n)), ("down", 1.0 / n)):
            if n == 1 and direction == "down":
                continue
            cents = 1200.0 * math.log2(ratio / scale)
            if best is None or abs(cents) < abs(best[0]):
                best = (cents, n, "none" if n == 1 else direction)  # type: ignore[assignment]
    assert best is not None
    cents_error, number, direction_found = best
    if abs(cents_error) > tolerance:
        return HarmonicResult(
            status="MISMATCH",
            reason="NOT_A_HARMONIC_RELATION",
            ratio=ratio,
            cents_error=cents_error,
        )
    if number == 1:
        return HarmonicResult(
            status="MATCH", ratio=ratio, cents_error=cents_error, harmonic_number=1
        )
    is_octave = number in _OCTAVE_FACTORS
    return HarmonicResult(
        status="OCTAVE_ERROR" if is_octave else "HARMONIC_ERROR",
        reason="OCTAVE_RELATION" if is_octave else "HARMONIC_RELATION",
        ratio=ratio,
        cents_error=cents_error,
        harmonic_number=number,
        direction=direction_found,
    )


def summarize_harmonic_confusion(
    expected_hz: object,
    detected_hz: object,
    tolerance_cents: object = DEFAULT_TOLERANCE_CENTS,
) -> HarmonicSummary:
    """Classify every pair and count the outcomes.

    ``CLEAR`` only when there is at least one pair and every pair matched. Any octave or
    harmonic error, or an unrelated mismatch, gives ``CONFUSION_FOUND``. Differing lengths,
    non-sequences, an empty list, or any invalid pair give ``INVALID_INPUT``.
    """
    for raw in (expected_hz, detected_hz):
        if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
            return HarmonicSummary(status="INVALID_INPUT", reason="NOT_A_SEQUENCE")
    assert isinstance(expected_hz, Sequence) and isinstance(detected_hz, Sequence)
    if len(expected_hz) != len(detected_hz):
        return HarmonicSummary(status="INVALID_INPUT", reason="LENGTH_MISMATCH")
    if not expected_hz:
        return HarmonicSummary(status="INVALID_INPUT", reason="EMPTY")
    counts = {"MATCH": 0, "OCTAVE_ERROR": 0, "HARMONIC_ERROR": 0, "MISMATCH": 0}
    for expected, detected in zip(expected_hz, detected_hz):
        result = classify_harmonic_confusion(expected, detected, tolerance_cents)
        if result.status == "INVALID_INPUT":
            return HarmonicSummary(status="INVALID_INPUT", reason=result.reason)
        counts[result.status] += 1
    total = len(expected_hz)
    bad = total - counts["MATCH"]
    return HarmonicSummary(
        status="CLEAR" if bad == 0 else "CONFUSION_FOUND",
        total=total,
        matches=counts["MATCH"],
        octave_errors=counts["OCTAVE_ERROR"],
        harmonic_errors=counts["HARMONIC_ERROR"],
        mismatches=counts["MISMATCH"],
        confusion_rate=bad / total,
    )
