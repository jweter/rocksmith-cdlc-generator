from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from rocksmith_cdlc_generator import private_product_reality_cli
from rocksmith_cdlc_generator.eof_recording_clock import (
    EOFProjectRecordingClockReport,
    EOFRecordingClockComparison,
)
from rocksmith_cdlc_generator.mobile_eof_differential import build_mobile_eof_differential
from rocksmith_cdlc_generator.mobile_product_reality import render_mobile_review
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


def test_cli_loader_uses_current_source_bound_report(monkeypatch: pytest.MonkeyPatch) -> None:
    eof_report = _report()
    project_dir = Path("/tmp/private-project")
    monkeypatch.setattr(
        private_product_reality_cli,
        "load_private_product_reality_scenario",
        lambda path: SimpleNamespace(project_dir=project_dir),
    )
    monkeypatch.setattr(
        private_product_reality_cli,
        "load_current_project_eof_recording_clock_report",
        lambda project: eof_report,
    )

    projection = private_product_reality_cli._load_mobile_review_eof_differential(
        Path("/tmp/scenario.json")
    )

    assert projection is not None
    assert projection["arrangement"] == "bass"
    assert projection["classification"] == "constant_offset"


def test_mobile_renderer_displays_sanitized_eof_differential() -> None:
    projection = build_mobile_eof_differential(_report())
    html = render_mobile_review(
        {
            "commit": "1" * 40,
            "scenario": "eof-mobile-path",
            "automated_result": "PASS",
            "failed_checks": [],
            "timeline_landmarks": [],
            "eof_differential": projection,
            "arrangements": [],
            "desktop_acceptance_debt": [],
        }
    )

    assert "EOF timing differential" in html
    assert "constant_offset" in html
    assert "0.125 s" in html
    assert "private note that must not escape" not in html
    assert "a" * 64 not in html
