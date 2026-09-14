from pathlib import Path

import pytest

from rocksmith_cdlc_generator.mobile_product_reality import (
    build_mobile_review_report,
    render_mobile_review,
)
from rocksmith_cdlc_generator.private_product_reality import (
    BuildObservation,
    CheckpointObservation,
    PrivateProductRealityScenario,
    RoleTimingObservation,
    SharedTimingExpectations,
    SharedTimingObservation,
    TimingCheckpoint,
    evaluate_shared_timing_observation,
)
from rocksmith_cdlc_generator.score_source import ArrangementRole

_HASH_A = "a" * 64
_HASH_B = "b" * 64
_HASH_C = "c" * 64
_HASH_D = "d" * 64


def _evidence(project: Path, *, first: float, checkpoint_observed: float):
    scenario = PrivateProductRealityScenario(
        scenario_id="mobile-adapter-regression",
        project_dir=project,
        expected=SharedTimingExpectations(first_playable_seconds=7.13),
        checkpoints=[
            TimingCheckpoint(
                id="later-structure",
                role=ArrangementRole.bass,
                source_time_seconds=70.0,
                expected_audio_seconds=77.80,
            )
        ],
        human_only_acceptance=["Judge final Rocksmith gameplay feel."],
    )
    observation = SharedTimingObservation(
        scenario_id=scenario.scenario_id,
        project_dir=str(project),
        observed_at_utc="2026-09-14T00:00:00+00:00",
        build=BuildObservation(
            version="0.1.0",
            commit_sha="1" * 40,
            built_at_utc="2026-09-14T00:00:00Z",
            packaged=True,
        ),
        tempo_beat_count=400,
        roles=[
            RoleTimingObservation(
                role=ArrangementRole.bass,
                source_track_index=0,
                first_source_seconds=4.0,
                first_playable_seconds=first,
                note_count=100,
                recording_sha256=_HASH_A,
                score_sha256=_HASH_B,
                source_output_sha256=_HASH_C,
                timing_points_sha256=_HASH_D,
            )
        ],
        checkpoints=[
            CheckpointObservation(
                checkpoint_id="later-structure",
                role=ArrangementRole.bass,
                source_time_seconds=70.0,
                expected_audio_seconds=77.80,
                observed_audio_seconds=checkpoint_observed,
            )
        ],
    )
    return evaluate_shared_timing_observation(scenario, observation, scenario_sha256="e" * 64)


def test_mobile_report_is_build_bound_responsive_and_escaped() -> None:
    html = render_mobile_review(
        {
            "commit": "abc123",
            "scenario": "synthetic timing <check>",
            "arrangements": [
                {
                    "name": "Bass",
                    "first_playable_seconds": 7.109,
                    "phase_beats": 0.0,
                    "drift_seconds": 0.0,
                }
            ],
            "desktop_acceptance_debt": ["Rocksmith 2014 playback"],
        }
    )
    assert 'name="viewport"' in html
    assert "abc123" in html
    assert "synthetic timing &lt;check&gt;" in html
    assert "Bass" in html
    assert "7.109" in html
    assert "Rocksmith 2014 playback" in html
    assert "does not verify packaging" in html


def test_mobile_report_preserves_three_first_class_arrangements() -> None:
    html = render_mobile_review(
        {
            "commit": "def456",
            "scenario": "three-arrangement parity",
            "human_result": "FLAG",
            "arrangements": [
                {"name": "Bass"},
                {"name": "Lead"},
                {"name": "Rhythm"},
            ],
        }
    )
    assert all(name in html for name in ("Bass", "Lead", "Rhythm"))
    assert "Human review: FLAG" in html


@pytest.mark.parametrize("field", ["commit", "scenario"])
def test_mobile_report_rejects_null_identity(field: str) -> None:
    report = {"commit": "abc123", "scenario": "identity-check"}
    report[field] = None

    with pytest.raises(ValueError, match=f"missing required field: {field}"):
        render_mobile_review(report)


def test_build_mobile_review_report_reuses_evaluated_evidence_not_new_math(tmp_path: Path) -> None:
    evidence = _evidence(tmp_path, first=7.12, checkpoint_observed=77.82)

    report = build_mobile_review_report(evidence)

    assert report["commit"] == "1" * 40
    assert report["scenario"] == "mobile-adapter-regression"
    assert report["desktop_acceptance_debt"] == ["Judge final Rocksmith gameplay feel."]
    assert report["arrangements"] == [
        {
            "name": "Bass",
            "first_playable_seconds": 7.12,
            "phase_beats": "UNKNOWN",
            "drift_seconds": pytest.approx(0.03, abs=1e-9),
        }
    ]
    # The renderer must accept this report shape unmodified.
    html = render_mobile_review(report)
    assert "Bass" in html
    assert "7.12" in html


def test_build_mobile_review_report_leaves_drift_unknown_without_checkpoints(tmp_path: Path) -> None:
    scenario = PrivateProductRealityScenario(
        scenario_id="mobile-adapter-no-checkpoints",
        project_dir=tmp_path,
        expected=SharedTimingExpectations(first_playable_seconds=7.13),
    )
    observation = SharedTimingObservation(
        scenario_id=scenario.scenario_id,
        project_dir=str(tmp_path),
        observed_at_utc="2026-09-14T00:00:00+00:00",
        build=BuildObservation(version="0.1.0", commit_sha=None, built_at_utc=None, packaged=False),
        tempo_beat_count=400,
        roles=[
            RoleTimingObservation(
                role=ArrangementRole.lead,
                source_track_index=1,
                first_source_seconds=4.0,
                first_playable_seconds=7.13,
                note_count=100,
                recording_sha256=_HASH_A,
                score_sha256=_HASH_B,
                source_output_sha256=_HASH_C,
                timing_points_sha256=_HASH_D,
            )
        ],
    )
    evidence = evaluate_shared_timing_observation(scenario, observation, scenario_sha256="e" * 64)

    report = build_mobile_review_report(evidence)

    assert report["commit"] == "unknown-build"
    assert report["arrangements"] == [
        {
            "name": "Lead",
            "first_playable_seconds": 7.13,
            "phase_beats": "UNKNOWN",
            "drift_seconds": "UNKNOWN",
        }
    ]
    # A missing commit/drift must still render as a valid, non-crashing artifact.
    assert render_mobile_review(report)
