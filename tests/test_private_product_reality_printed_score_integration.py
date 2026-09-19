from __future__ import annotations

from pathlib import Path

from rocksmith_cdlc_generator.private_product_reality import (
    BuildObservation,
    PrivateProductRealityScenario,
    RoleTimingObservation,
    SharedTimingExpectations,
    SharedTimingObservation,
    evaluate_shared_timing_observation,
)
from rocksmith_cdlc_generator.product_reality_printed_score import (
    PrintedScoreProductRealityEvidence,
)
from rocksmith_cdlc_generator.score_source import ArrangementRole


HASH = "a" * 64


def _scenario(tmp_path: Path) -> PrivateProductRealityScenario:
    return PrivateProductRealityScenario(
        scenario_id="printed-score-runner-integration",
        project_dir=tmp_path,
        roles=[ArrangementRole.bass],
        expected=SharedTimingExpectations(first_playable_seconds=1.0),
    )


def _observation(
    scenario: PrivateProductRealityScenario,
    printed_score_recognition: PrintedScoreProductRealityEvidence,
) -> SharedTimingObservation:
    return SharedTimingObservation(
        scenario_id=scenario.scenario_id,
        project_dir=str(scenario.project_dir),
        observed_at_utc="2026-09-19T00:40:00+00:00",
        build=BuildObservation(
            version="test",
            commit_sha="b" * 40,
            packaged=True,
        ),
        tempo_beat_count=2,
        roles=[
            RoleTimingObservation(
                role=ArrangementRole.bass,
                source_track_index=0,
                first_source_seconds=1.0,
                first_playable_seconds=1.0,
                note_count=1,
                recording_sha256=HASH,
                score_sha256=HASH,
                source_output_sha256=HASH,
                timing_points_sha256=HASH,
            )
        ],
        printed_score_recognition=printed_score_recognition,
    )


def test_fully_reviewed_printed_score_recognition_is_embedded_as_runner_check(
    tmp_path: Path,
) -> None:
    scenario = _scenario(tmp_path)
    printed_score_recognition = PrintedScoreProductRealityEvidence(
        status="PASS",
        candidate_page_count=2,
        reviewed_page_count=2,
        unreadable_candidate_count=0,
        mean_clean_measure_fraction=1.0,
        mean_low_confidence_event_fraction=0.0,
        message="All 2 printed-score recognition candidate page(s) have completed human review.",
    )

    evidence = evaluate_shared_timing_observation(
        scenario,
        _observation(scenario, printed_score_recognition),
        scenario_sha256=HASH,
    )

    check = next(item for item in evidence.checks if item.code == "printed_score_recognition")
    assert check.status == "PASS"
    assert evidence.printed_score_recognition == printed_score_recognition
    assert evidence.result == "PASS"


def test_unreviewed_printed_score_recognition_holds_runner_at_review_required(
    tmp_path: Path,
) -> None:
    scenario = _scenario(tmp_path)
    printed_score_recognition = PrintedScoreProductRealityEvidence(
        status="REVIEW_REQUIRED",
        candidate_page_count=2,
        reviewed_page_count=1,
        unreadable_candidate_count=0,
        mean_clean_measure_fraction=0.5,
        mean_low_confidence_event_fraction=0.1,
        message="1 of 2 printed-score recognition candidate page(s) still require human review before promotion.",
    )

    evidence = evaluate_shared_timing_observation(
        scenario,
        _observation(scenario, printed_score_recognition),
        scenario_sha256=HASH,
    )

    check = next(item for item in evidence.checks if item.code == "printed_score_recognition")
    assert check.status == "REVIEW_REQUIRED"
    assert evidence.result == "REVIEW_REQUIRED"
