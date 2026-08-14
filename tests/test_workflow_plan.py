from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import rocksmith_cdlc_generator.workflow_plan as workflow_plan
from rocksmith_cdlc_generator.alignment import AlignmentReport
from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTrack,
)


def _inventory(project: Path, **overrides):
    values = {
        "project_path": str(project),
        "local_sources": [],
        "local_audio_sources": 1,
        "unresolved_rights_reviews": 0,
        "reference_count": 0,
        "selected_reference": False,
        "reviewed_recording_context": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _write_imported_source(
    project: Path,
    relative: str,
    *,
    instrument: str = "bass",
    source_sha256: str = "a" * 64,
    track_index: int = 0,
) -> SimpleNamespace:
    path = project / relative
    source = ImportedSource(
        provenance=SourceProvenance(
            source_type="test",
            source_filename=path.name,
            source_sha256=source_sha256,
            importer="test",
            importer_version="1",
        ),
        tracks=[
            SourceTrack(
                source_track_index=track_index,
                name=f"{instrument} track",
                instrument=instrument,
                notes=[
                    SourceNoteEvent(
                        start_seconds=0.0,
                        duration_seconds=0.5,
                        midi=40,
                        import_confidence=1.0,
                    )
                ],
            )
        ],
    )
    source.write_json(path)
    return SimpleNamespace(
        family="notation",
        parser_pending=False,
        output_relative_path=relative,
    )


def _write_alignment(project: Path, source_path: Path, *, source_sha256: str, track_index: int = 0) -> None:
    report = AlignmentReport(
        source_path=str(source_path.resolve()),
        source_sha256=source_sha256,
        track_index=track_index,
        audio_beat_start_index=0,
        global_offset_seconds=0.0,
        anchor_stride_beats=8,
        matched_beats=4,
        rms_residual_seconds=0.0,
        median_abs_residual_seconds=0.0,
        max_abs_residual_seconds=0.0,
        confidence=1.0,
        anchors=[],
        regions=[],
    )
    destination = project / "analysis" / "alignment.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(report.model_dump_json(indent=2), encoding="utf-8")


def test_plan_starts_with_automatic_normalization_when_source_is_ready(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "song"
    project.mkdir()
    monkeypatch.setattr(workflow_plan, "build_project_source_inventory", lambda _: _inventory(project))

    plan = workflow_plan.build_project_workflow_plan(project)

    assert plan.next_step_id == "normalize"
    normalize = next(step for step in plan.steps if step.step_id == "normalize")
    assert normalize.status == "ready"
    assert normalize.mode == "automatic"
    assert normalize.command and "cdlc normalize" in normalize.command


def test_plan_keeps_rights_confirmation_as_human_blocker(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "song"
    project.mkdir()
    monkeypatch.setattr(
        workflow_plan,
        "build_project_source_inventory",
        lambda _: _inventory(project, unresolved_rights_reviews=1),
    )

    plan = workflow_plan.build_project_workflow_plan(project)

    assert plan.next_step_id == "source-rights"
    rights = next(step for step in plan.steps if step.step_id == "source-rights")
    assert rights.status == "blocked"
    assert rights.mode == "human"
    assert plan.human_blocking_steps >= 1


def test_single_bass_source_becomes_automatic_alignment_and_reconciliation(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "song"
    (project / "analysis").mkdir(parents=True)
    (project / "analysis" / "tempo_map.json").write_text("{}", encoding="utf-8")
    (project / "analysis" / "bass_raw.json").write_text("{}", encoding="utf-8")
    source = _write_imported_source(project, "sources/imported/song.json", track_index=3)
    monkeypatch.setattr(
        workflow_plan,
        "build_project_source_inventory",
        lambda _: _inventory(project, local_sources=[source]),
    )

    plan = workflow_plan.build_project_workflow_plan(project)

    align = next(step for step in plan.steps if step.step_id == "align-tab")
    reconcile = next(step for step in plan.steps if step.step_id == "reconcile-tab")
    assert align.status == "ready"
    assert align.mode == "automatic"
    assert align.command and "align-source" in align.command
    assert "--track-index 3" in align.command
    assert reconcile.status == "blocked"
    assert reconcile.mode == "automatic"


def test_lead_source_is_not_used_as_bass_alignment_input(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "song"
    source = _write_imported_source(project, "sources/imported/lead.json", instrument="lead")
    monkeypatch.setattr(
        workflow_plan,
        "build_project_source_inventory",
        lambda _: _inventory(project, local_sources=[source]),
    )

    plan = workflow_plan.build_project_workflow_plan(project)

    align = next(step for step in plan.steps if step.step_id == "align-tab")
    assert align.status == "optional"
    assert align.command is None
    assert "No existing parsed Bass symbolic source" in align.reason


def test_missing_imported_artifact_is_not_planned_for_alignment(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "song"
    project.mkdir()
    stale = SimpleNamespace(
        family="notation",
        parser_pending=False,
        output_relative_path="sources/imported/missing.json",
    )
    monkeypatch.setattr(
        workflow_plan,
        "build_project_source_inventory",
        lambda _: _inventory(project, local_sources=[stale]),
    )

    plan = workflow_plan.build_project_workflow_plan(project)

    align = next(step for step in plan.steps if step.step_id == "align-tab")
    assert align.status == "optional"
    assert align.command is None


def test_multiple_bass_sources_require_human_source_choice(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "song"
    project.mkdir()
    sources = [
        _write_imported_source(project, "sources/imported/a.json", source_sha256="a" * 64),
        _write_imported_source(project, "sources/imported/b.json", source_sha256="b" * 64),
    ]
    monkeypatch.setattr(
        workflow_plan,
        "build_project_source_inventory",
        lambda _: _inventory(project, local_sources=sources),
    )

    plan = workflow_plan.build_project_workflow_plan(project)

    align = next(step for step in plan.steps if step.step_id == "align-tab")
    assert align.status == "blocked"
    assert align.mode == "human"
    assert "2 imported Bass sources" in align.reason


def test_existing_alignment_resolves_choice_among_multiple_bass_sources(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "song"
    (project / "analysis").mkdir(parents=True)
    (project / "analysis" / "bass_raw.json").write_text("{}", encoding="utf-8")
    source_a = _write_imported_source(project, "sources/imported/a.json", source_sha256="a" * 64)
    source_b = _write_imported_source(project, "sources/imported/b.json", source_sha256="b" * 64)
    _write_alignment(
        project,
        project / "sources/imported/b.json",
        source_sha256="b" * 64,
    )
    monkeypatch.setattr(
        workflow_plan,
        "build_project_source_inventory",
        lambda _: _inventory(project, local_sources=[source_a, source_b]),
    )

    plan = workflow_plan.build_project_workflow_plan(project)

    align = next(step for step in plan.steps if step.step_id == "align-tab")
    reconcile = next(step for step in plan.steps if step.step_id == "reconcile-tab")
    assert align.status == "complete"
    assert reconcile.status == "ready"
    assert reconcile.command and "sources" in reconcile.command and "b.json" in reconcile.command


def test_alignment_for_non_bass_track_does_not_resolve_bass_source_choice(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "song"
    bass = _write_imported_source(project, "sources/imported/bass.json", source_sha256="a" * 64)
    lead = _write_imported_source(
        project,
        "sources/imported/lead.json",
        instrument="lead",
        source_sha256="b" * 64,
    )
    _write_alignment(
        project,
        project / "sources/imported/lead.json",
        source_sha256="b" * 64,
    )
    monkeypatch.setattr(
        workflow_plan,
        "build_project_source_inventory",
        lambda _: _inventory(project, local_sources=[bass, lead]),
    )

    plan = workflow_plan.build_project_workflow_plan(project)

    align = next(step for step in plan.steps if step.step_id == "align-tab")
    assert align.status in {"ready", "blocked"}
    assert align.command is None or "bass.json" in align.command


def test_plan_progresses_to_human_review_after_validation(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "song"
    for relative in [
        "audio/normalized.wav",
        "analysis/tempo_map.json",
        "analysis/bass_raw.json",
        "charts/bass_mapped.json",
        "review/validation_report.json",
    ]:
        path = project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
    monkeypatch.setattr(workflow_plan, "build_project_source_inventory", lambda _: _inventory(project))

    plan = workflow_plan.build_project_workflow_plan(project)

    review = next(step for step in plan.steps if step.step_id == "human-review")
    assert review.status == "ready"
    assert review.mode == "human"
    assert plan.next_step_id == "human-review"
