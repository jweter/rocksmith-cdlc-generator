from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.eof_recording_clock import (
    EOFProjectRecordingClockReport,
    EOFRecordingClockComparison,
)
from rocksmith_cdlc_generator.mobile_eof_differential import build_mobile_eof_differential
from rocksmith_cdlc_generator.score_source import ArrangementRole


def _report(**comparison_overrides: object) -> EOFProjectRecordingClockReport:
    comparison_payload: dict[str, object] = {
        "classification": "constant_offset",
        "first_playable_delta_seconds": 0.125,
        "median_abs_error_seconds": 0.12,
        "max_abs_error_seconds": 0.14,
        "delta_spread_seconds": 0.02,
        "results": [],
    }
    comparison_payload.update(comparison_overrides)
    return EOFProjectRecordingClockReport(
        instrument=ArrangementRole.bass,
        score_sha256="a" * 64,
        recording_sha256="b" * 64,
        source_track_index=0,
        fixture_id="private-eof-fixture",
        fixture_sha256="c" * 64,
        eof_version="1.8RC12",
        evidence_note="private note that must not escape",
        shared_timeline_sha256="d" * 64,
        timing_tolerance_seconds=0.15,
        comparison=EOFRecordingClockComparison.model_validate(comparison_payload),
    )


def test_mobile_eof_differential_projects_only_sanitized_aggregate_evidence() -> None:
    projection = build_mobile_eof_differential(_report())

    assert projection == {
        "arrangement": "bass",
        "classification": "constant_offset",
        "first_playable_delta_seconds": 0.125,
        "median_abs_error_seconds": 0.12,
        "max_abs_error_seconds": 0.14,
        "delta_spread_seconds": 0.02,
        "timing_tolerance_seconds": 0.15,
        "matched": True,
    }
    assert "evidence_note" not in projection
    assert "score_sha256" not in projection
    assert "recording_sha256" not in projection
    assert "results" not in projection


def test_mobile_eof_differential_fails_closed_on_nonfinite_aggregate() -> None:
    report = _report(max_abs_error_seconds=float("inf"))

    with pytest.raises(ValueError, match="non-finite EOF differential field: max_abs_error_seconds"):
        build_mobile_eof_differential(report)
