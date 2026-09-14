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
from rocksmith_cdlc_generator.product_reality_official_tab import OfficialTabProductRealityEvidence
from rocksmith_cdlc_generator.score_source import ArrangementRole


HASH = "a" * 64


def _scenario(tmp_path: Path) -> PrivateProductRealityScenario:
    return PrivateProductRealityScenario(
        scenario_id="official-tab-runner-integration",
        project_dir=tmp_path,
        roles=[ArrangementRole.bass],
        expected=SharedTimingExpectations(first_playable_seconds=1.0),
    )


def _observation(
    scenario: PrivateProductRealityScenario,
    official_tab: OfficialTabProductRealityEvidence,
) -> SharedTimingObservation:
    return SharedTimingObservation(
        scenario_id=scenario.scenario_id,
        project_dir=str(scenario.project_dir),
        observed_at_utc="2026-09-14T00:40:00+00:00",
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
        official_tab_registration=official_tab,
    )


def test_registered_official_tab_pass_is_embedded_as_runner_check(tmp_path: Path) -> None:
    scenario = _scenario(tmp_path)
    official_tab = OfficialTabProductRealityEvidence(
        status="PASS",
        checked_at_utc="2026-09-14T00:39:00+00:00",
        page_count=2,
        message="Official TAB registration matches current project state.",
    )

    evidence = evaluate_shared_timing_observation(
        scenario,
        _observation(scenario, official_tab),
        scenario_sha256=HASH,
    )

    check = next(item for item in evidence.checks if item.code == "official_tab_registration")
    assert check.status == "PASS"
    assert evidence.official_tab_registration == official_tab
    assert evidence.result == "PASS"


def test_official_tab_drift_fails_runner_without_private_detail(tmp_path: Path) -> None:
    scenario = _scenario(tmp_path)
    official_tab = OfficialTabProductRealityEvidence(
        status="FAIL",
        checked_at_utc="2026-09-14T00:39:00+00:00",
        page_count=2,
        drift_codes=["page_hash_changed"],
        message="Official TAB registration drift was detected against current project state.",
    )

    evidence = evaluate_shared_timing_observation(
        scenario,
        _observation(scenario, official_tab),
        scenario_sha256=HASH,
    )

    check = next(item for item in evidence.checks if item.code == "official_tab_registration")
    assert check.status == "FAIL"
    assert check.message == "Official TAB registration drift was detected against current project state."
    assert evidence.result == "FAIL"
