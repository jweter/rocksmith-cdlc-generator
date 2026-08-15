from __future__ import annotations

from pathlib import Path

from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.song_workspace import build_song_workspace_snapshot
from rocksmith_cdlc_generator.validation import ReviewItem, ValidationReport
from rocksmith_cdlc_generator.workflow_plan import ProjectWorkflowPlan, WorkflowStep


def _project(tmp_path: Path) -> Path:
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
        arrangement_instruments=["bass", "lead", "rhythm"],
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
