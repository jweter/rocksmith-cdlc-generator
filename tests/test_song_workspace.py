from __future__ import annotations

from pathlib import Path

from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.score_source import (
    ArrangementRole,
    ProjectScoreSource,
    ScoreArrangementMapping,
    ScoreTrackCandidate,
)
from rocksmith_cdlc_generator.song_workspace import build_song_workspace_snapshot
from rocksmith_cdlc_generator.validation import ReviewItem, ValidationReport
from rocksmith_cdlc_generator.workflow_plan import ProjectWorkflowPlan, WorkflowStep


def _project(tmp_path: Path, *, instruments: list[str] | None = None) -> Path:
    project = tmp_path / "song"
    project.mkdir()
    for relative in ("source", "analysis", "charts", "review", "eof", "sources"):
        (project / relative).mkdir(parents=True, exist_ok=True)
    source = project / "source" / "song.wav"
    source.write_bytes(b"fixture")
    manifest = ProjectManifest(
        project_name="Example Artist - Example Song",
        artist="Example Artist",
        title="Example Song",
        arrangement_instruments=instruments if instruments is not None else ["bass", "lead", "rhythm"],
        source_original_path=str(source),
        source_project_path="source/song.wav",
        source_sha256="1" * 64,
        source_metadata=AudioMetadata(
            duration_seconds=120.0,
            sample_rate_hz=44100,
            channels=2,
            codec_name="pcm_s16le",
            format_name="wav",
        ),
    )
    manifest.save(project)
    return project


def _register_confirmed_lead_mapping(project: Path) -> None:
    """Write a registered score contract with a human-confirmed Lead mapping.

    Mirrors what ``cdlc-score-map confirm lead <index>`` persists -- deliberately
    without touching ``project.json``'s ``arrangement_instruments``, since neither
    that CLI command nor ``score_mapping_review.confirm_score_mapping`` update it.
    """

    stored = project / "sources" / "score" / "original" / "song.gp5"
    stored.parent.mkdir(parents=True, exist_ok=True)
    stored.write_bytes(b"complete-score")
    score = ProjectScoreSource(
        source_filename="song.gp5",
        source_sha256=sha256_file(stored),
        source_format="gp5",
        imported_relative_path=str(stored.relative_to(project)),
        tracks=[
            ScoreTrackCandidate(source_track_index=0, name="Lead Guitar", note_count=100),
            ScoreTrackCandidate(source_track_index=1, name="Bass", note_count=90),
        ],
        arrangement_mappings=[
            ScoreArrangementMapping(
                role=ArrangementRole.lead,
                source_track_index=0,
                confidence=0.0,
                basis=["human selected score track explicitly"],
                human_confirmed=True,
            ),
        ],
    )
    score.write_json(project / "sources" / "score" / "source.json")


def _plan(project: Path, *, human: int, automatic: int, complete: int = 1) -> ProjectWorkflowPlan:
    steps = [
        WorkflowStep(
            step_id=f"done-{index}",
            title="Completed step",
            status="complete",
            mode="automatic",
            reason="fixture",
        )
        for index in range(complete)
    ]
    if human:
        steps.append(
            WorkflowStep(
                step_id="human-review",
                title="Review timing",
                status="blocked",
                mode="human",
                reason="Human timing review is required.",
            )
        )
    elif automatic:
        steps.append(
            WorkflowStep(
                step_id="automatic-work",
                title="Build draft",
                status="ready",
                mode="automatic",
                command='cdlc tempo "fixture" --engine librosa',
                reason="Ready to continue.",
            )
        )
    return ProjectWorkflowPlan(
        project_path=str(project),
        steps=steps,
        next_step_id=steps[-1].step_id if len(steps) > complete else None,
        automatic_ready_steps=automatic,
        human_blocking_steps=human,
    )


def _write_pass_validation(project: Path, role: str) -> None:
    report = ValidationReport(
        status="PASS",
        can_package=True,
        fail_count=0,
        warning_count=0,
        review_queue=[],
    )
    name = "validation_report.json" if role == "bass" else f"{role}_validation_report.json"
    (project / "review" / name).write_text(report.model_dump_json(indent=2), encoding="utf-8")


def test_workspace_surfaces_human_gate_without_mutating_project(tmp_path: Path, monkeypatch) -> None:
    project = _project(tmp_path)
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.song_workspace.build_multi_arrangement_workflow_plan",
        lambda _project: _plan(project, human=1, automatic=0, complete=2),
    )

    before = sorted(path.relative_to(project).as_posix() for path in project.rglob("*"))
    snapshot = build_song_workspace_snapshot(project)
    after = sorted(path.relative_to(project).as_posix() for path in project.rglob("*"))

    assert snapshot.health == "REVIEW"
    assert snapshot.next_step_id == "human-review"
    assert snapshot.next_action_title == "Review timing"
    assert snapshot.human_blocking_steps == 1
    assert snapshot.sources.recording_sha256 == "1" * 64
    assert [item.role for item in snapshot.arrangements] == ["bass", "lead", "rhythm"]
    assert before == after


def test_workspace_combines_arrangement_validation_into_one_review_queue(tmp_path: Path, monkeypatch) -> None:
    project = _project(tmp_path)
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.song_workspace.build_multi_arrangement_workflow_plan",
        lambda _project: _plan(project, human=0, automatic=1, complete=3),
    )

    bass = ValidationReport(
        status="WARNING",
        can_package=True,
        fail_count=0,
        warning_count=1,
        review_queue=[
            ReviewItem(
                code="bass_note_requires_review",
                severity="WARNING",
                stage="transcription",
                message="Bass note needs review.",
                time_seconds=10.0,
                note_index=4,
                priority=65,
            )
        ],
    )
    lead = ValidationReport(
        status="FAIL",
        can_package=False,
        fail_count=1,
        warning_count=0,
        review_queue=[
            ReviewItem(
                code="unresolved_guitar_position",
                severity="FAIL",
                stage="guitar_authoring",
                message="Lead note has no exportable position.",
                time_seconds=22.5,
                priority=100,
            )
        ],
    )
    (project / "review" / "validation_report.json").write_text(
        bass.model_dump_json(indent=2), encoding="utf-8"
    )
    (project / "review" / "lead_validation_report.json").write_text(
        lead.model_dump_json(indent=2), encoding="utf-8"
    )

    snapshot = build_song_workspace_snapshot(project)

    assert snapshot.health == "BLOCKED"
    assert [(item.arrangement, item.severity) for item in snapshot.review_queue] == [
        ("lead", "FAIL"),
        ("bass", "WARNING"),
    ]
    lead_state = next(item for item in snapshot.arrangements if item.role == "lead")
    assert lead_state.validation_state == "FAIL"
    assert lead_state.fail_count == 1


def _repeated_warning(index: int) -> ReviewItem:
    return ReviewItem(
        code="source_pitch_conflict",
        severity="WARNING",
        stage="reconciliation",
        message="Symbolic and audio-derived notes occur together but disagree on MIDI pitch.",
        time_seconds=float(index),
        priority=90,
    )


def test_workspace_pairs_actionable_warning_groups_with_raw_event_totals(
    tmp_path: Path, monkeypatch
) -> None:
    """#375: a project with thousands of raw repeated warnings that group to a
    handful of actionable root causes must expose both counts -- the raw
    machine-readable total for audit/provenance, and the human-facing actionable
    group count -- reconciling exactly with the persisted detailed queue. FAIL
    counts stay individually explicit and are never folded into the grouping.
    """
    project = _project(tmp_path)
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.song_workspace.build_multi_arrangement_workflow_plan",
        lambda _project: _plan(project, human=0, automatic=1, complete=3),
    )

    # Bass: one FAIL (stays individual) plus 2851 raw WARNING events that all share
    # one (severity, stage, code) root cause -- exactly the Product Reality shape
    # from the #375 report (Bass 2851 raw warnings, only 1 actionable group).
    bass_fail = ReviewItem(
        code="unmapped_bass_note",
        severity="FAIL",
        stage="mapping",
        message="Bass note 10 has no playable string/fret position.",
        time_seconds=4.0,
        note_index=10,
        priority=100,
    )
    bass_warnings = [_repeated_warning(index) for index in range(2851)]
    bass = ValidationReport(
        status="FAIL",
        can_package=False,
        fail_count=1,
        warning_count=len(bass_warnings),
        review_queue=[bass_fail, *bass_warnings],
    )
    (project / "review" / "validation_report.json").write_text(
        bass.model_dump_json(indent=2), encoding="utf-8"
    )

    # Lead: 2046 raw warnings across 3 distinct root causes -> 3 actionable groups.
    lead_warnings = (
        [_repeated_warning(index) for index in range(2000)]
        + [
            ReviewItem(
                code="low_guitar_alignment_confidence",
                severity="WARNING",
                stage="alignment",
                message="Lead alignment confidence is low.",
                time_seconds=1.0,
                priority=80,
            )
            for _ in range(30)
        ]
        + [
            ReviewItem(
                code="unsupported_imported_technique",
                severity="WARNING",
                stage="authoring",
                message="Lead note contains an unsupported technique.",
                time_seconds=2.0,
                priority=72,
            )
            for _ in range(16)
        ]
    )
    lead = ValidationReport(
        status="WARNING",
        can_package=True,
        fail_count=0,
        warning_count=len(lead_warnings),
        review_queue=lead_warnings,
    )
    (project / "review" / "lead_validation_report.json").write_text(
        lead.model_dump_json(indent=2), encoding="utf-8"
    )

    snapshot = build_song_workspace_snapshot(project)

    bass_state = next(item for item in snapshot.arrangements if item.role == "bass")
    lead_state = next(item for item in snapshot.arrangements if item.role == "lead")

    # Raw machine-readable totals are preserved exactly -- nothing is dropped.
    assert bass_state.warning_count == 2851
    assert lead_state.warning_count == 2046

    # Actionable/grouped counts reflect distinct root causes, not raw event volume.
    assert bass_state.fail_count == 1
    assert bass_state.actionable_warning_count == 1
    assert lead_state.actionable_warning_count == 3

    # The combined review queue is already the grouped/actionable presentation
    # queue (#365/#367): total actionable WARNING rows across arrangements matches
    # the per-arrangement actionable counts exactly, while every FAIL stays
    # individual and explicit rather than being hidden behind grouping.
    actionable_warning_rows = [item for item in snapshot.review_queue if item.severity == "WARNING"]
    fail_rows = [item for item in snapshot.review_queue if item.severity == "FAIL"]
    assert len(actionable_warning_rows) == 1 + 3
    assert len(fail_rows) == 1

    # The snapshot-level raw total reconciles exactly with the sum of the
    # per-arrangement raw totals -- no double counting, no silently dropped events.
    assert snapshot.raw_warning_event_count == 2851 + 2046


def test_workspace_reports_ready_only_for_current_validated_exports(tmp_path: Path, monkeypatch) -> None:
    project = _project(tmp_path)
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.song_workspace.build_multi_arrangement_workflow_plan",
        lambda _project: _plan(project, human=0, automatic=0, complete=4),
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.song_workspace._draft_state",
        lambda _project, _role: "CURRENT",
    )
    for role in ("bass", "lead", "rhythm"):
        _write_pass_validation(project, role)
        (project / "eof" / f"arr_{role}_RS2.xml").write_text("<song />", encoding="utf-8")

    snapshot = build_song_workspace_snapshot(project)

    assert snapshot.health == "READY"
    assert all(item.export_xml_ready for item in snapshot.arrangements)
    assert snapshot.review_queue == []


def test_stale_draft_keeps_existing_xml_from_reporting_ready(tmp_path: Path, monkeypatch) -> None:
    project = _project(tmp_path)
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.song_workspace.build_multi_arrangement_workflow_plan",
        lambda _project: _plan(project, human=0, automatic=1, complete=3),
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.song_workspace._draft_state",
        lambda _project, role: "PRESENT" if role.value == "lead" else "CURRENT",
    )
    for role in ("bass", "lead", "rhythm"):
        _write_pass_validation(project, role)
        (project / "eof" / f"arr_{role}_RS2.xml").write_text("<song />", encoding="utf-8")

    snapshot = build_song_workspace_snapshot(project)

    lead = next(item for item in snapshot.arrangements if item.role == "lead")
    assert lead.draft_state == "PRESENT"
    assert not lead.export_xml_ready
    assert snapshot.health == "IN_PROGRESS"


def test_pending_workflow_prevents_ready_even_with_current_validated_exports(tmp_path: Path, monkeypatch) -> None:
    project = _project(tmp_path)
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.song_workspace.build_multi_arrangement_workflow_plan",
        lambda _project: _plan(project, human=0, automatic=1, complete=4),
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.song_workspace._draft_state",
        lambda _project, _role: "CURRENT",
    )
    for role in ("bass", "lead", "rhythm"):
        _write_pass_validation(project, role)
        (project / "eof" / f"arr_{role}_RS2.xml").write_text("<song />", encoding="utf-8")

    snapshot = build_song_workspace_snapshot(project)

    assert all(item.export_xml_ready for item in snapshot.arrangements)
    assert snapshot.complete_steps < snapshot.total_steps
    assert snapshot.health == "IN_PROGRESS"


def test_unreadable_validation_report_blocks_old_xml_readiness(tmp_path: Path, monkeypatch) -> None:
    project = _project(tmp_path)
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.song_workspace.build_multi_arrangement_workflow_plan",
        lambda _project: _plan(project, human=0, automatic=0, complete=4),
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.song_workspace._draft_state",
        lambda _project, _role: "CURRENT",
    )
    for role in ("bass", "lead", "rhythm"):
        _write_pass_validation(project, role)
        (project / "eof" / f"arr_{role}_RS2.xml").write_text("<song />", encoding="utf-8")

    (project / "review" / "lead_validation_report.json").write_text("{truncated", encoding="utf-8")

    snapshot = build_song_workspace_snapshot(project)

    lead = next(item for item in snapshot.arrangements if item.role == "lead")
    assert snapshot.health == "BLOCKED"
    assert lead.validation_state == "INVALID"
    assert lead.validation_problem is not None
    assert "Re-run validation" in lead.validation_problem
    assert not lead.export_xml_ready
    assert any(
        item.arrangement == "lead"
        and item.code == "invalid_validation_report"
        and item.severity == "FAIL"
        and item.priority == 100
        for item in snapshot.review_queue
    )


def test_human_confirmed_mapping_marks_undeclared_role_configured(tmp_path: Path, monkeypatch) -> None:
    """#304: a role becomes real project work once its score mapping is human-confirmed,
    even for a bass-only CLI project (``cdlc new --instrument bass``) whose
    ``arrangement_instruments`` was never updated -- neither ``cdlc-score-map confirm``
    nor ``confirm_score_mapping`` touch that manifest field, but the mapping confirmation
    alone is what ``multi_arrangement_plan._confirmed_guitar_roles`` uses to build real
    Lead/Rhythm workflow steps and validation reports. ``configured`` must track the same
    signal, or a genuinely FAIL/INVALID Lead validation report for a role the user is
    actively confirming gets silently excluded from ``configured_arrangements`` (the set
    the validation dashboard and export-readiness gate both treat as "the project").
    """

    project = _project(tmp_path, instruments=["bass"])
    _register_confirmed_lead_mapping(project)
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.song_workspace.build_multi_arrangement_workflow_plan",
        lambda _project: _plan(project, human=0, automatic=1, complete=2),
    )

    snapshot = build_song_workspace_snapshot(project)

    bass_state = next(item for item in snapshot.arrangements if item.role == "bass")
    lead_state = next(item for item in snapshot.arrangements if item.role == "lead")
    rhythm_state = next(item for item in snapshot.arrangements if item.role == "rhythm")
    assert bass_state.configured
    assert lead_state.configured
    assert not rhythm_state.configured


def test_human_confirmed_role_invalid_report_still_blocks_health(tmp_path: Path, monkeypatch) -> None:
    """The same undeclared-but-confirmed Lead role must still gate overall project
    health when its persisted validation evidence is unreadable -- exactly the
    protection ``test_unreadable_validation_report_blocks_old_xml_readiness`` already
    covers for a manifest-declared role. Pre-fix, ``any_validation_problem`` was only
    raised for roles inside ``manifest.arrangement_instruments``, so this INVALID Lead
    report was silently dropped and health stayed unblocked.
    """

    project = _project(tmp_path, instruments=["bass"])
    _register_confirmed_lead_mapping(project)
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.song_workspace.build_multi_arrangement_workflow_plan",
        lambda _project: _plan(project, human=0, automatic=0, complete=2),
    )
    _write_pass_validation(project, "bass")
    (project / "review" / "lead_validation_report.json").write_text("{truncated", encoding="utf-8")

    snapshot = build_song_workspace_snapshot(project)

    assert snapshot.health == "BLOCKED"
