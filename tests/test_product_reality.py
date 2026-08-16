from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.product_reality import (
    ACTIVE_SESSION_PATH,
    add_product_reality_observation,
    finish_product_reality_session,
    increment_product_reality_correction,
    load_active_product_reality_session,
    product_reality_live_metrics,
    product_reality_pass_evidence_gaps,
    start_product_reality_session,
    start_product_reality_stage,
    stop_product_reality_stage,
)
from rocksmith_cdlc_generator.score_source import ProjectScoreSource, ScoreTrackCandidate


def _project(tmp_path: Path, *, with_score: bool = True) -> Path:
    project = tmp_path / "song"
    project.mkdir()
    ProjectManifest(
        project_name="reality-test",
        title="Reality Test",
        arrangement_instruments=["bass", "lead", "rhythm"],
        source_original_path="C:/private/song.wav",
        source_project_path="audio/source.wav",
        source_sha256="a" * 64,
        source_metadata=AudioMetadata(
            duration_seconds=240.0,
            sample_rate_hz=48000,
            channels=2,
            codec_name="pcm_s16le",
            format_name="wav",
        ),
    ).save(project)
    if with_score:
        score = ProjectScoreSource(
            source_filename="score.gp5",
            source_sha256="b" * 64,
            source_format="gp5",
            imported_relative_path="sources/score/score.gp5",
            tracks=[
                ScoreTrackCandidate(
                    source_track_index=0,
                    name="Bass",
                    instrument_hint="bass",
                    note_count=10,
                )
            ],
        )
        score.write_json(project / "sources" / "score" / "source.json")
    return project


def test_session_records_stage_time_corrections_observations_and_reports(tmp_path: Path) -> None:
    project = _project(tmp_path)
    start = datetime(2026, 8, 15, 14, 0, tzinfo=timezone.utc)

    session = start_product_reality_session(
        project,
        packaged_build_id="gha-123",
        started_at=start,
    )
    assert session.project_source_sha256 == "a" * 64
    assert session.score_sha256 == "b" * 64
    assert session.score_format == "gp5"

    start_product_reality_stage(
        project,
        name="shared timing review",
        counts_as_editing=True,
        started_at=start + timedelta(minutes=2),
    )
    session = stop_product_reality_stage(
        project,
        completed_at=start + timedelta(minutes=10),
    )
    assert session.editing_seconds == pytest.approx(480.0)
    assert session.editing_minutes_per_finished_minute == pytest.approx(2.0)

    increment_product_reality_correction(project, arrangement="lead", category="timing")
    session = increment_product_reality_correction(
        project,
        arrangement="lead",
        category="timing",
    )
    assert session.total_corrections == 2
    assert session.corrections[0].count == 2

    session = add_product_reality_observation(
        project,
        area="arrangement preview",
        severity="friction",
        text="Dense preview redraw felt slow.",
        requires_cli_or_powershell=True,
        recorded_at=start + timedelta(minutes=11),
    )
    assert session.cli_workaround_count == 1

    completed, json_path, markdown_path = finish_product_reality_session(
        project,
        result="fail",
        reason="Normal path still requires a CLI workaround.",
        completed_at=start + timedelta(minutes=12),
    )
    assert completed.gate_result == "fail"
    assert completed.editing_minutes_per_finished_minute == pytest.approx(2.0)
    assert json_path.is_file()
    assert markdown_path.is_file()
    assert "Editing minutes per finished minute: 2.000" in markdown_path.read_text(encoding="utf-8")
    assert "CLI/PowerShell workaround" in markdown_path.read_text(encoding="utf-8")
    assert not (project / ACTIVE_SESSION_PATH).exists()


def test_live_metrics_include_running_editing_stage_without_persisting_it(tmp_path: Path) -> None:
    project = _project(tmp_path)
    start = datetime(2026, 8, 15, 14, 0, tzinfo=timezone.utc)
    start_product_reality_session(project, started_at=start)
    session = start_product_reality_stage(
        project,
        name="arrangement review",
        counts_as_editing=True,
        started_at=start + timedelta(minutes=1),
    )

    metrics = product_reality_live_metrics(session, now=start + timedelta(minutes=4))

    assert metrics.active_stage_elapsed_seconds == pytest.approx(180.0)
    assert metrics.measured_work_seconds == pytest.approx(180.0)
    assert metrics.editing_seconds == pytest.approx(180.0)
    assert metrics.editing_minutes_per_finished_minute == pytest.approx(0.75)
    persisted = load_active_product_reality_session(project)
    assert persisted is not None
    assert persisted.stages == []
    assert persisted.measured_work_seconds == 0.0
    assert persisted.editing_seconds == 0.0


def test_live_metrics_do_not_count_nonediting_active_stage_as_editing(tmp_path: Path) -> None:
    project = _project(tmp_path)
    start = datetime(2026, 8, 15, 14, 0, tzinfo=timezone.utc)
    start_product_reality_session(project, started_at=start)
    session = start_product_reality_stage(
        project,
        name="validation / export",
        counts_as_editing=False,
        started_at=start + timedelta(minutes=1),
    )

    metrics = product_reality_live_metrics(session, now=start + timedelta(minutes=3))

    assert metrics.active_stage_elapsed_seconds == pytest.approx(120.0)
    assert metrics.measured_work_seconds == pytest.approx(120.0)
    assert metrics.editing_seconds == 0.0
    assert metrics.editing_minutes_per_finished_minute == 0.0


def test_live_metrics_reject_clock_before_active_stage_start(tmp_path: Path) -> None:
    project = _project(tmp_path)
    start = datetime(2026, 8, 15, 14, 0, tzinfo=timezone.utc)
    start_product_reality_session(project, started_at=start)
    session = start_product_reality_stage(
        project,
        name="timing",
        counts_as_editing=True,
        started_at=start + timedelta(minutes=2),
    )

    with pytest.raises(ValueError, match="live clock cannot precede"):
        product_reality_live_metrics(session, now=start + timedelta(minutes=1))


def test_session_without_registered_score_is_still_recordable(tmp_path: Path) -> None:
    project = _project(tmp_path, with_score=False)
    session = start_product_reality_session(project)
    assert session.score_sha256 is None
    assert session.score_format is None


def test_active_stage_must_stop_before_session_completion(tmp_path: Path) -> None:
    project = _project(tmp_path)
    start_product_reality_session(project)
    start_product_reality_stage(project, name="arrangement review", counts_as_editing=True)

    with pytest.raises(ValueError, match="Stop the active"):
        finish_product_reality_session(project, result="pass", reason="Not actually complete")


def test_second_session_or_stage_cannot_start_while_one_is_active(tmp_path: Path) -> None:
    project = _project(tmp_path)
    start_product_reality_session(project)
    with pytest.raises(ValueError, match="already active"):
        start_product_reality_session(project)

    start_product_reality_stage(project, name="timing", counts_as_editing=True)
    with pytest.raises(ValueError, match="already running"):
        start_product_reality_stage(project, name="editing", counts_as_editing=True)


def test_pass_fail_requires_explicit_reason(tmp_path: Path) -> None:
    project = _project(tmp_path)
    start_product_reality_session(project)
    with pytest.raises(ValueError, match="explicit reason"):
        finish_product_reality_session(project, result="pass", reason="   ")
    assert load_active_product_reality_session(project) is not None


def test_pass_evidence_gaps_identify_missing_baseline_and_block_pass(tmp_path: Path) -> None:
    project = _project(tmp_path, with_score=False)
    session = start_product_reality_session(project)

    assert product_reality_pass_evidence_gaps(session) == (
        "packaged build / artifact identity",
        "registered complete score identity",
        "completed workflow stage timing",
        "measured human editing interval",
        "usability / responsiveness observation",
    )

    with pytest.raises(ValueError, match="PASS requires baseline evidence"):
        finish_product_reality_session(project, result="pass", reason="Looks good")
    assert load_active_product_reality_session(project) is not None


def test_fail_remains_recordable_when_pass_evidence_is_incomplete(tmp_path: Path) -> None:
    project = _project(tmp_path, with_score=False)
    start_product_reality_session(project)

    completed, _json_path, _markdown_path = finish_product_reality_session(
        project,
        result="fail",
        reason="Could not complete the required evidence run.",
    )

    assert completed.gate_result == "fail"


def test_pass_requires_no_cli_workaround_or_blocker_and_accepts_complete_baseline(tmp_path: Path) -> None:
    project = _project(tmp_path)
    start = datetime(2026, 8, 15, 14, 0, tzinfo=timezone.utc)
    start_product_reality_session(project, packaged_build_id="windows-466", started_at=start)
    start_product_reality_stage(
        project,
        name="arrangement review / correction",
        counts_as_editing=True,
        started_at=start + timedelta(minutes=1),
    )
    stop_product_reality_stage(project, completed_at=start + timedelta(minutes=3))
    session = add_product_reality_observation(
        project,
        area="playback / arrangement preview",
        severity="note",
        text="Playback and preview remained responsive during repeated edits.",
        recorded_at=start + timedelta(minutes=4),
    )

    assert product_reality_pass_evidence_gaps(session) == ()
    completed, _json_path, _markdown_path = finish_product_reality_session(
        project,
        result="pass",
        reason="Baseline packaged workflow evidence completed without blockers or hidden repair steps.",
        completed_at=start + timedelta(minutes=5),
    )
    assert completed.gate_result == "pass"


def test_pass_evidence_flags_cli_workaround_and_blocker(tmp_path: Path) -> None:
    project = _project(tmp_path)
    start = datetime(2026, 8, 15, 14, 0, tzinfo=timezone.utc)
    start_product_reality_session(project, packaged_build_id="windows-466", started_at=start)
    start_product_reality_stage(
        project,
        name="arrangement review / correction",
        counts_as_editing=True,
        started_at=start + timedelta(minutes=1),
    )
    stop_product_reality_stage(project, completed_at=start + timedelta(minutes=2))
    session = add_product_reality_observation(
        project,
        area="validation",
        severity="blocker",
        text="Required manual repair outside the GUI.",
        requires_cli_or_powershell=True,
        recorded_at=start + timedelta(minutes=3),
    )

    gaps = product_reality_pass_evidence_gaps(session)
    assert "normal path without CLI / PowerShell workaround" in gaps
    assert "no unresolved blocker observation" in gaps
