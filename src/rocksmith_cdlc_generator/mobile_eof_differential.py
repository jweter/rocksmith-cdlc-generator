"""Privacy-safe projection of EOF recording-clock parity evidence for mobile review."""

from __future__ import annotations

from math import isfinite
from typing import Any

from .eof_recording_clock import EOFProjectRecordingClockReport


def _finite_or_none(value: float | None, *, field: str) -> float | None:
    if value is None:
        return None
    if not isfinite(value):
        raise ValueError(f"non-finite EOF differential field: {field}")
    return value


def build_mobile_eof_differential(report: EOFProjectRecordingClockReport) -> dict[str, Any]:
    """Return only derived EOF parity evidence suitable for a mobile artifact.

    The projection deliberately excludes source paths, score/audio payloads,
    workspace data, individual note/fret observations, and free-form private
    evidence notes. It exposes only deterministic aggregate timing evidence
    already derived by the authoritative EOF recording-clock comparator.
    """

    comparison = report.comparison
    return {
        "arrangement": report.instrument.value,
        "classification": comparison.classification,
        "first_playable_delta_seconds": _finite_or_none(
            comparison.first_playable_delta_seconds,
            field="first_playable_delta_seconds",
        ),
        "median_abs_error_seconds": _finite_or_none(
            comparison.median_abs_error_seconds,
            field="median_abs_error_seconds",
        ),
        "max_abs_error_seconds": _finite_or_none(
            comparison.max_abs_error_seconds,
            field="max_abs_error_seconds",
        ),
        "delta_spread_seconds": _finite_or_none(
            comparison.delta_spread_seconds,
            field="delta_spread_seconds",
        ),
        "timing_tolerance_seconds": _finite_or_none(
            report.timing_tolerance_seconds,
            field="timing_tolerance_seconds",
        ),
        "matched": report.matched,
    }
