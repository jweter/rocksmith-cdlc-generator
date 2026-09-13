from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator import private_product_reality
from rocksmith_cdlc_generator.build_staging import PsarcRegistrationDrift, PsarcRegistrationVerification
from rocksmith_cdlc_generator.private_product_reality import (
    BuildObservation,
    CheckpointObservation,
    PrivateProductRealityEvidence,
    PrivateProductRealityScenario,
    RoleTimingObservation,
    SharedTimingExpectations,
    SharedTimingObservation,
    TimingCheckpoint,
    collect_shared_timing_observation,
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


def _psarc_verification(status: str, drift: list[PsarcRegistrationDrift] | None = None) -> PsarcRegistrationVerification:
    return PsarcRegistrationVerification(
        status=status,
        checked_at_utc="2026-09-13T03:00:00+00:00",
        receipt_path="/project/build/staging/psarc_receipt.json",
        psarc_path="/project/build/staging/song.psarc",
        build_readiness_path="/project/build/staging/build_readiness.json",
        dlcbuilder_project_path="/project/build/dlcbuilder/song.rs2dlc",
        drift=drift or [],
    )


def test_passing_psarc_registration_becomes_a_deterministic_pass_check(tmp_path: Path) -> None:
    scenario = _scenario(tmp_path)
    observation = _observation(tmp_path, first=7.12, checkpoint=77.82).model_copy(
        update={"psarc_registration": _psarc_verification("PASS")}
    )

    evidence = evaluate_shared_timing_observation(scenario, observation, scenario_sha256="e" * 64)

    check = next(check for check in evidence.checks if check.code == "psarc_registration")
    assert check.status == "PASS"
    assert evidence.result == "PASS"
    assert evidence.psarc_registration is not None
    assert evidence.psarc_registration.status == "PASS"


def test_drifted_psarc_registration_fails_the_scenario_automatically(tmp_path: Path) -> None:
    scenario = _scenario(tmp_path)
    drift = [PsarcRegistrationDrift(code="psarc_hash_changed", message="Staged PSARC contents changed")]
    observation = _observation(tmp_path, first=7.12, checkpoint=77.82).model_copy(
        update={"psarc_registration": _psarc_verification("FAIL", drift)}
    )

    evidence = evaluate_shared_timing_observation(scenario, observation, scenario_sha256="e" * 64)

    check = next(check for check in evidence.checks if check.code == "psarc_registration")
    assert check.status == "FAIL"
    assert "psarc_hash_changed" in check.message
    assert evidence.result == "FAIL"


def test_unregistered_psarc_adds_no_check_and_does_not_block_a_pure_timing_scenario(tmp_path: Path) -> None:
    """A project that has not reached the packaging stage yet must still PASS on timing alone."""

    scenario = _scenario(tmp_path)
    observation = _observation(tmp_path, first=7.12, checkpoint=77.82)
    assert observation.psarc_registration is None

    evidence = evaluate_shared_timing_observation(scenario, observation, scenario_sha256="e" * 64)

    assert not any(check.code == "psarc_registration" for check in evidence.checks)
    assert evidence.result == "PASS"


def test_collect_shared_timing_observation_skips_psarc_check_when_never_registered(
    tmp_path: Path,
) -> None:
    scenario = _scenario(tmp_path)

    observation = collect_shared_timing_observation(scenario)

    assert observation.psarc_registration is None
    assert not any("PSARC" in error for error in observation.collection_errors)


def test_collect_shared_timing_observation_wires_in_verify_psarc_registration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario = _scenario(tmp_path)
    verification = _psarc_verification("PASS")
    monkeypatch.setattr(
        private_product_reality,
        "verify_psarc_registration",
        lambda project: verification,
    )

    observation = collect_shared_timing_observation(scenario)

    assert observation.psarc_registration == verification


def test_collect_shared_timing_observation_reports_unreadable_receipt_as_review_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario = _scenario(tmp_path)

    def _broken(project: Path) -> PsarcRegistrationVerification:
        raise OSError("receipt disk read failed")

    monkeypatch.setattr(private_product_reality, "verify_psarc_registration", _broken)

    observation = collect_shared_timing_observation(scenario)

    assert observation.psarc_registration is None
    assert any("PSARC registration receipt is unreadable" in error for error in observation.collection_errors)
