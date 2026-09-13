from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.private_product_reality import (
    BuildObservation,
    CheckpointObservation,
    PrivateProductRealityEvidence,
    PrivateProductRealityScenario,
    RoleTimingObservation,
    SharedTimingExpectations,
    SharedTimingObservation,
    TimingCheckpoint,
    evaluate_shared_timing_observation,
    load_private_product_reality_scenario,
)
from rocksmith_cdlc_generator.score_source import ArrangementRole

_HASH_A = "a" * 64
_HASH_B = "b" * 64
_HASH_C = "c" * 64
_HASH_D = "d" * 64


def _scenario(project: Path) -> PrivateProductRealityScenario:
    return PrivateProductRealityScenario(
        scenario_id="shared-timing-regression",
        project_dir=project,
        expected=SharedTimingExpectations(
            first_playable_seconds=7.13,
            first_playable_tolerance_seconds=0.20,
            max_arrangement_spread_seconds=0.05,
            max_checkpoint_error_seconds=0.20,
            max_drift_seconds=0.20,
        ),
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


def _role(role: ArrangementRole, first: float, *, transform_hash: str = _HASH_D) -> RoleTimingObservation:
    return RoleTimingObservation(
        role=role,
        source_track_index={
            ArrangementRole.bass: 0,
            ArrangementRole.lead: 1,
            ArrangementRole.rhythm: 2,
        }[role],
        first_source_seconds=4.0,
        first_playable_seconds=first,
        note_count=100,
        recording_sha256=_HASH_A,
        score_sha256=_HASH_B,
        source_output_sha256=_HASH_C,
        timing_points_sha256=transform_hash,
    )


def _observation(project: Path, *, first: float, checkpoint: float) -> SharedTimingObservation:
    return SharedTimingObservation(
        scenario_id="shared-timing-regression",
        project_dir=str(project),
        observed_at_utc="2026-09-13T03:00:00+00:00",
        build=BuildObservation(
            version="0.1.0",
            commit_sha="1" * 40,
            built_at_utc="2026-09-13T02:55:00Z",
            packaged=True,
        ),
        project_recording_sha256=_HASH_A,
        tempo_map_path=str(project / "analysis" / "tempo_map.json"),
        tempo_map_sha256=_HASH_C,
        tempo_beat_count=400,
        roles=[
            _role(ArrangementRole.bass, first),
            _role(ArrangementRole.lead, first + 0.01),
            _role(ArrangementRole.rhythm, first + 0.02),
        ],
        checkpoints=[
            CheckpointObservation(
                checkpoint_id="later-structure",
                role=ArrangementRole.bass,
                source_time_seconds=70.0,
                expected_audio_seconds=77.80,
                observed_audio_seconds=checkpoint,
            )
        ],
    )


def test_shared_timing_pass_needs_no_human_for_deterministic_facts(tmp_path: Path) -> None:
    scenario = _scenario(tmp_path)
    observation = _observation(tmp_path, first=7.12, checkpoint=77.82)

    evidence = evaluate_shared_timing_observation(
        scenario,
        observation,
        scenario_sha256="e" * 64,
    )

    assert evidence.result == "PASS"
    assert all(check.status == "PASS" for check in evidence.checks)
    assert evidence.human_only_acceptance == ["Judge final Rocksmith gameplay feel."]


def test_two_measure_constant_phase_regression_fails_automatically(tmp_path: Path) -> None:
    """Regression shape from #431/#455: every arrangement is about 4.64 s late."""

    scenario = _scenario(tmp_path)
    observation = _observation(tmp_path, first=11.77, checkpoint=82.44)

    evidence = evaluate_shared_timing_observation(
        scenario,
        observation,
        scenario_sha256="e" * 64,
    )

    assert evidence.result == "FAIL"
    first_checks = {
        check.code: check.status
        for check in evidence.checks
        if check.code.endswith("_first_event")
    }
    assert first_checks == {
        "bass_first_event": "FAIL",
        "lead_first_event": "FAIL",
        "rhythm_first_event": "FAIL",
    }
    checkpoint = next(check for check in evidence.checks if check.code == "checkpoint_later-structure")
    assert checkpoint.status == "FAIL"


def test_incomplete_or_unbound_evidence_fails_closed_to_review_required(tmp_path: Path) -> None:
    scenario = _scenario(tmp_path)
    observation = SharedTimingObservation(
        scenario_id=scenario.scenario_id,
        project_dir=str(tmp_path),
        observed_at_utc="2026-09-13T03:00:00+00:00",
        build=BuildObservation(
            version="0.1.0",
            commit_sha=None,
            built_at_utc=None,
            packaged=False,
        ),
        tempo_beat_count=None,
        roles=[_role(ArrangementRole.bass, 7.13)],
        collection_errors=[
            "lead reviewed timing authority is unavailable or stale",
            "rhythm reviewed timing authority is unavailable or stale",
        ],
    )

    evidence = evaluate_shared_timing_observation(
        scenario,
        observation,
        scenario_sha256="e" * 64,
    )

    assert evidence.result == "REVIEW_REQUIRED"
    assert next(check for check in evidence.checks if check.code == "build_identity").status == "REVIEW_REQUIRED"
    assert next(check for check in evidence.checks if check.code == "shared_timing_transform").status == "REVIEW_REQUIRED"


def test_transform_disagreement_is_a_deterministic_failure(tmp_path: Path) -> None:
    scenario = _scenario(tmp_path)
    observation = _observation(tmp_path, first=7.13, checkpoint=77.80)
    observation = observation.model_copy(
        update={
            "roles": [
                _role(ArrangementRole.bass, 7.13),
                _role(ArrangementRole.lead, 7.14),
                _role(ArrangementRole.rhythm, 7.15, transform_hash="f" * 64),
            ]
        }
    )

    evidence = evaluate_shared_timing_observation(
        scenario,
        observation,
        scenario_sha256="e" * 64,
    )

    assert evidence.result == "FAIL"
    shared = next(check for check in evidence.checks if check.code == "shared_timing_transform")
    assert shared.status == "FAIL"


def test_scenario_project_path_is_relative_to_private_scenario_file(tmp_path: Path) -> None:
    private_root = tmp_path / "private"
    private_root.mkdir()
    project = private_root / "song-project"
    scenario_path = private_root / "scenario.json"
    scenario_path.write_text(
        PrivateProductRealityScenario(
            scenario_id="relative-project",
            project_dir=Path("song-project"),
            expected=SharedTimingExpectations(first_playable_seconds=1.0),
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )

    loaded = load_private_product_reality_scenario(scenario_path)

    assert loaded.project_dir == project.resolve()


def test_evidence_history_refuses_to_overwrite_a_prior_run(tmp_path: Path) -> None:
    evidence = PrivateProductRealityEvidence(
        scenario_id="append-only",
        observed_at_utc="2026-09-13T03:00:00+00:00",
        scenario_sha256="e" * 64,
        result="PASS",
        build=BuildObservation(
            version="0.1.0",
            commit_sha="1" * 40,
            built_at_utc=None,
            packaged=False,
        ),
        checks=[],
    )
    destination = tmp_path / "evidence.json"

    evidence.write_json(destination)
    with pytest.raises(FileExistsError, match="append-only"):
        evidence.write_json(destination)
