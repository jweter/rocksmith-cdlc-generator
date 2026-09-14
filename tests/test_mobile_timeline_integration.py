from __future__ import annotations

from types import SimpleNamespace

import pytest

from rocksmith_cdlc_generator.mobile_product_reality import (
    build_mobile_review_report,
    render_mobile_review,
)
from rocksmith_cdlc_generator.mobile_timeline import build_mobile_timeline_landmarks
from rocksmith_cdlc_generator.score_source import ArrangementRole


def test_mobile_review_report_and_html_include_sanitized_timeline_landmarks() -> None:
    evidence = SimpleNamespace(
        checks=[],
        role_observations=[
            SimpleNamespace(role=ArrangementRole.bass, first_playable_seconds=7.125),
        ],
        checkpoint_observations=[
            SimpleNamespace(
                role=ArrangementRole.bass,
                checkpoint_id="chorus-entry",
                observed_audio_seconds=77.80,
                expected_audio_seconds=77.75,
            )
        ],
        build=SimpleNamespace(commit_sha="1" * 40),
        scenario_id="timeline-product-path",
        scenario_sha256="a" * 64,
        observed_at_utc="2026-09-14T00:00:00Z",
        project_recording_sha256="b" * 64,
        tempo_map_sha256="c" * 64,
        result="PASS",
        human_only_acceptance=[],
    )

    report = build_mobile_review_report(evidence)

    assert report["timeline_landmarks"] == [
        {
            "kind": "first_playable",
            "arrangement": "bass",
            "id": "bass:first_playable",
            "seconds": 7.125,
        },
        {
            "kind": "checkpoint",
            "arrangement": "bass",
            "id": "chorus-entry",
            "seconds": 77.80,
            "expected_seconds": 77.75,
        },
    ]

    html = render_mobile_review(report)
    assert "Timeline landmarks" in html
    assert "bass:first_playable" in html
    assert "chorus-entry" in html
    assert "77.8 s" in html


def test_mobile_timeline_rejects_nonfinite_expected_checkpoint_time() -> None:
    evidence = SimpleNamespace(
        role_observations=[],
        checkpoint_observations=[
            SimpleNamespace(
                role=ArrangementRole.lead,
                checkpoint_id="overflow",
                observed_audio_seconds=10.0,
                expected_audio_seconds=float("inf"),
            )
        ],
    )

    with pytest.raises(ValueError, match="invalid mobile timeline timestamp"):
        build_mobile_timeline_landmarks(evidence)
