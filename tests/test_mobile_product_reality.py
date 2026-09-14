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


def _role_observation(role: ArrangementRole, first: float, *, source_track_index: int = 0):
    return RoleTimingObservation(
        role=role,
        source_track_index=source_track_index,
        first_source_seconds=4.0,
        first_playable_seconds=first,
        note_count=100,
        recording_sha256=_HASH_A,
        score_sha256=_HASH_B,
        source_output_sha256=_HASH_C,
        timing_points_sha256=_HASH_D,
    )


def _evidence(
    project: Path,
    *,
    first: float,
    checkpoint_observed: float,
    roles: list[ArrangementRole] | None = None,
):
    scenario = PrivateProductRealityScenario(
        scenario_id="mobile-adapter-regression",
        project_dir=project,
        roles=roles or [ArrangementRole.bass],
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
        roles=[_role_observation(ArrangementRole.bass, first)],
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
    # Omitted automated_result/failed_checks must default to a visible, non-crashing state that
    # never claims checks passed when no result was actually supplied.
    assert "Automated result: UNKNOWN" in html
    assert "No deterministic check results were supplied." in html
    assert "All deterministic checks passed." not in html
    # A commit/scenario without a scenario hash must still render, showing the gap honestly.
    assert "<strong>Scenario hash:</strong> UNKNOWN" in html


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


def test_mobile_report_surfaces_automated_result_and_failed_checks() -> None:
    html = render_mobile_review(
        {
            "commit": "abc123",
            "scenario": "identity-check",
            "scenario_sha256": "f" * 64,
            "automated_result": "FAIL",
            "failed_checks": [
                {"code": "bass_first_event", "status": "FAIL", "message": "late by 4.640s"},
            ],
        }
    )
    assert "Automated result: FAIL" in html
    assert "bass_first_event" in html
    assert "late by 4.640s" in html
    assert f"<strong>Scenario hash:</strong> {'f' * 64}" in html
    # A FAIL with individual checks listed must not also claim a clean pass.
    assert "All deterministic checks passed." not in html


def test_mobile_report_does_not_claim_pass_when_result_fails_with_no_listed_checks() -> None:
    """Regression for Codex P2: an inconsistent FAIL/empty-checks input must stay honest."""

    html = render_mobile_review(
        {
            "commit": "abc123",
            "scenario": "identity-check",
            "automated_result": "REVIEW_REQUIRED",
        }
    )
    assert "Automated result: REVIEW_REQUIRED" in html
    assert "No deterministic check results were supplied." in html
    assert "All deterministic checks passed." not in html


@pytest.mark.parametrize("field", ["commit", "scenario"])
def test_mobile_report_rejects_null_identity(field: str) -> None:
    report = {"commit": "abc123", "scenario": "identity-check"}
    report[field] = None

    with pytest.raises(ValueError, match=f"missing required field: {field}"):
        render_mobile_review(report)


def test_mobile_report_rejects_unsupported_automated_result() -> None:
    report = {"commit": "abc123", "scenario": "identity-check", "automated_result": "MAYBE"}

    with pytest.raises(ValueError, match="unsupported automated_result: MAYBE"):
        render_mobile_review(report)


def test_build_mobile_review_report_reuses_evaluated_evidence_not_new_math(tmp_path: Path) -> None:
    evidence = _evidence(tmp_path, first=7.12, checkpoint_observed=77.82)

    report = build_mobile_review_report(evidence)

    assert report["commit"] == "1" * 40
    assert report["scenario"] == "mobile-adapter-regression"
    assert report["scenario_sha256"] == "e" * 64
    assert report["automated_result"] == "PASS"
    assert report["failed_checks"] == []
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
    assert "Automated result: PASS" in html


def test_build_mobile_review_report_leaves_drift_unknown_without_checkpoints(tmp_path: Path) -> None:
    scenario = PrivateProductRealityScenario(
        scenario_id="mobile-adapter-no-checkpoints",
        project_dir=tmp_path,
        roles=[ArrangementRole.lead],
        expected=SharedTimingExpectations(first_playable_seconds=7.13),
    )
    observation = SharedTimingObservation(
        scenario_id=scenario.scenario_id,
        project_dir=str(tmp_path),
        observed_at_utc="2026-09-14T00:00:00+00:00",
        build=BuildObservation(version="0.1.0", commit_sha=None, built_at_utc=None, packaged=False),
        tempo_beat_count=400,
        roles=[_role_observation(ArrangementRole.lead, 7.13, source_track_index=1)],
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


def test_build_mobile_review_report_keeps_card_for_role_with_failed_collection(tmp_path: Path) -> None:
    """Regression for Codex P2: a role whose observation collection failed must not vanish."""

    scenario = PrivateProductRealityScenario(
        scenario_id="mobile-adapter-missing-role",
        project_dir=tmp_path,
        roles=[ArrangementRole.bass, ArrangementRole.lead],
        expected=SharedTimingExpectations(first_playable_seconds=7.13),
    )
    observation = SharedTimingObservation(
        scenario_id=scenario.scenario_id,
        project_dir=str(tmp_path),
        observed_at_utc="2026-09-14T00:00:00+00:00",
        build=BuildObservation(
            version="0.1.0", commit_sha="1" * 40, built_at_utc="2026-09-14T00:00:00Z", packaged=True
        ),
        tempo_beat_count=400,
        roles=[_role_observation(ArrangementRole.bass, 7.12)],
        collection_errors=["lead reviewed timing authority is unavailable or stale"],
    )
    evidence = evaluate_shared_timing_observation(scenario, observation, scenario_sha256="e" * 64)
    assert evidence.result == "REVIEW_REQUIRED"

    report = build_mobile_review_report(evidence)

    names = [item["name"] for item in report["arrangements"]]
    assert names == ["Bass", "Lead"]
    lead_card = next(item for item in report["arrangements"] if item["name"] == "Lead")
    assert lead_card["first_playable_seconds"] == "UNKNOWN"
    assert report["automated_result"] == "REVIEW_REQUIRED"
    assert any(check["code"] == "lead_first_event" for check in report["failed_checks"])
    # A vanished Lead card would silently hide incomplete Bass/Lead/Rhythm coverage.
    html = render_mobile_review(report)
    assert "Lead" in html


def test_build_mobile_review_report_selects_worst_of_multiple_checkpoint_drifts(tmp_path: Path) -> None:
    """Regression for Codex P2: picking only the last checkpoint can hide a real regression."""

    scenario = PrivateProductRealityScenario(
        scenario_id="mobile-adapter-multi-checkpoint",
        project_dir=tmp_path,
        roles=[ArrangementRole.bass],
        expected=SharedTimingExpectations(first_playable_seconds=7.13, max_drift_seconds=0.5),
        checkpoints=[
            TimingCheckpoint(
                id="early-structure",
                role=ArrangementRole.bass,
                source_time_seconds=30.0,
                expected_audio_seconds=37.0,
            ),
            TimingCheckpoint(
                id="later-structure",
                role=ArrangementRole.bass,
                source_time_seconds=70.0,
                expected_audio_seconds=77.80,
            ),
        ],
    )
    observation = SharedTimingObservation(
        scenario_id=scenario.scenario_id,
        project_dir=str(tmp_path),
        observed_at_utc="2026-09-14T00:00:00+00:00",
        build=BuildObservation(
            version="0.1.0", commit_sha="1" * 40, built_at_utc="2026-09-14T00:00:00Z", packaged=True
        ),
        tempo_beat_count=400,
        roles=[_role_observation(ArrangementRole.bass, 7.13)],
        checkpoints=[
            # Early checkpoint has a large drift; the later (last-in-list) checkpoint recovers.
            # Selecting only the last entry would hide the worse early-structure regression.
            CheckpointObservation(
                checkpoint_id="early-structure",
                role=ArrangementRole.bass,
                source_time_seconds=30.0,
                expected_audio_seconds=37.0,
                observed_audio_seconds=37.40,
            ),
            CheckpointObservation(
                checkpoint_id="later-structure",
                role=ArrangementRole.bass,
                source_time_seconds=70.0,
                expected_audio_seconds=77.80,
                observed_audio_seconds=77.81,
            ),
        ],
    )
    evidence = evaluate_shared_timing_observation(scenario, observation, scenario_sha256="e" * 64)

    report = build_mobile_review_report(evidence)

    drift = report["arrangements"][0]["drift_seconds"]
    assert isinstance(drift, str)
    assert "worst of 2" in drift
    assert "early-structure" in drift


def test_build_mobile_review_report_ignores_checkpoint_id_that_looks_like_a_role_check(
    tmp_path: Path,
) -> None:
    """Regression for Codex P2: a checkpoint id ending in "_first_event" must not fabricate a card.

    `checkpoint_{id}` becomes the check code `checkpoint_bass_first_event` for a checkpoint id of
    "bass_first_event", which also matches the `{role}_first_event` suffix test used to discover
    requested roles. Only the real `bass_first_event` role check should produce a card.
    """

    scenario = PrivateProductRealityScenario(
        scenario_id="mobile-adapter-phantom-role",
        project_dir=tmp_path,
        roles=[ArrangementRole.bass],
        expected=SharedTimingExpectations(first_playable_seconds=7.13),
        checkpoints=[
            TimingCheckpoint(
                id="bass_first_event",
                role=ArrangementRole.bass,
                source_time_seconds=70.0,
                expected_audio_seconds=77.80,
            )
        ],
    )
    observation = SharedTimingObservation(
        scenario_id=scenario.scenario_id,
        project_dir=str(tmp_path),
        observed_at_utc="2026-09-14T00:00:00+00:00",
        build=BuildObservation(
            version="0.1.0", commit_sha="1" * 40, built_at_utc="2026-09-14T00:00:00Z", packaged=True
        ),
        tempo_beat_count=400,
        roles=[_role_observation(ArrangementRole.bass, 7.13)],
        checkpoints=[
            CheckpointObservation(
                checkpoint_id="bass_first_event",
                role=ArrangementRole.bass,
                source_time_seconds=70.0,
                expected_audio_seconds=77.80,
                observed_audio_seconds=77.80,
            )
        ],
    )
    evidence = evaluate_shared_timing_observation(scenario, observation, scenario_sha256="e" * 64)
    # Sanity check that the collision actually exists in the evidence this test exercises.
    assert "checkpoint_bass_first_event" in {check.code for check in evidence.checks}

    report = build_mobile_review_report(evidence)

    names = [item["name"] for item in report["arrangements"]]
    assert names == ["Bass"]


def test_build_mobile_review_report_does_not_confuse_checkpoint_ids_that_collide_on_drift_code(
    tmp_path: Path,
) -> None:
    """Regression for Codex P2: a checkpoint id ending in "_drift" must not corrupt another's drift.

    `checkpoint_{id}` becomes the check code `checkpoint_verse_drift` for a checkpoint id of
    "verse_drift", which collides with checkpoint "verse"'s own `checkpoint_verse_drift` *drift*
    check. A naive checks_by_code[f"checkpoint_{id}_drift"] lookup would silently pick whichever
    of the two same-named checks evidence.checks happened to list last -- here, "verse_drift"'s own
    large absolute-time error (not a drift at all) -- and could mislabel it under "verse", which in
    reality drifted by only 0.03s.
    """

    scenario = PrivateProductRealityScenario(
        scenario_id="mobile-adapter-drift-code-collision",
        project_dir=tmp_path,
        roles=[ArrangementRole.bass],
        expected=SharedTimingExpectations(first_playable_seconds=7.13, max_drift_seconds=30.0),
        checkpoints=[
            TimingCheckpoint(
                id="verse",
                role=ArrangementRole.bass,
                source_time_seconds=30.0,
                expected_audio_seconds=37.0,
            ),
            TimingCheckpoint(
                id="verse_drift",
                role=ArrangementRole.bass,
                source_time_seconds=70.0,
                expected_audio_seconds=77.80,
            ),
        ],
    )
    observation = SharedTimingObservation(
        scenario_id=scenario.scenario_id,
        project_dir=str(tmp_path),
        observed_at_utc="2026-09-14T00:00:00+00:00",
        build=BuildObservation(
            version="0.1.0", commit_sha="1" * 40, built_at_utc="2026-09-14T00:00:00Z", packaged=True
        ),
        tempo_beat_count=400,
        roles=[_role_observation(ArrangementRole.bass, 7.13)],
        checkpoints=[
            # "verse" drifted by a small, clean 0.03s.
            CheckpointObservation(
                checkpoint_id="verse",
                role=ArrangementRole.bass,
                source_time_seconds=30.0,
                expected_audio_seconds=37.0,
                observed_audio_seconds=37.03,
            ),
            # "verse_drift" has a large absolute-time error, unrelated to "verse"'s measurement.
            CheckpointObservation(
                checkpoint_id="verse_drift",
                role=ArrangementRole.bass,
                source_time_seconds=70.0,
                expected_audio_seconds=77.80,
                observed_audio_seconds=99.0,
            ),
        ],
    )
    evidence = evaluate_shared_timing_observation(scenario, observation, scenario_sha256="e" * 64)
    # Sanity check that the code-string collision actually exists in this evidence.
    collision_codes = [check.code for check in evidence.checks if check.code == "checkpoint_verse_drift"]
    assert len(collision_codes) == 2

    report = build_mobile_review_report(evidence)

    drift = report["arrangements"][0]["drift_seconds"]
    assert drift == "+21.200 (worst of 2, checkpoint 'verse_drift')"


def test_build_mobile_review_report_sanitizes_collection_error_messages(tmp_path: Path) -> None:
    """Regression for Codex P2: raw exception text (e.g. local paths) must not reach the artifact."""

    private_path = str(tmp_path / "private-songs" / "MySecretSong" / "manifest.json")
    scenario = PrivateProductRealityScenario(
        scenario_id="mobile-adapter-sanitize-collection",
        project_dir=tmp_path,
        roles=[ArrangementRole.bass],
        expected=SharedTimingExpectations(first_playable_seconds=7.13),
    )
    observation = SharedTimingObservation(
        scenario_id=scenario.scenario_id,
        project_dir=str(tmp_path),
        observed_at_utc="2026-09-14T00:00:00+00:00",
        build=BuildObservation(
            version="0.1.0", commit_sha="1" * 40, built_at_utc="2026-09-14T00:00:00Z", packaged=True
        ),
        tempo_beat_count=400,
        roles=[],
        collection_errors=[
            f"bass reviewed timing authority is unavailable or stale: "
            f"[Errno 2] No such file or directory: '{private_path}'"
        ],
    )
    evidence = evaluate_shared_timing_observation(scenario, observation, scenario_sha256="e" * 64)
    assert private_path in evidence.checks[-1].message  # raw evidence really does carry the path

    report = build_mobile_review_report(evidence)

    collection_check = next(check for check in report["failed_checks"] if check["code"] == "collection_1")
    assert private_path not in collection_check["message"]
    assert "MySecretSong" not in collection_check["message"]
    html = render_mobile_review(report)
    assert private_path not in html
    assert "MySecretSong" not in html
