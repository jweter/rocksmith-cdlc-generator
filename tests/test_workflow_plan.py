from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import rocksmith_cdlc_generator.workflow_plan as workflow_plan
from rocksmith_cdlc_generator.alignment import AlignmentReport
from rocksmith_cdlc_generator.alignment_leading_rest_refinement import (
    LEADING_REST_REFINEMENT_PATH,
    LeadingRestAlignmentRefinement,
)
from rocksmith_cdlc_generator.alignment_onset_refinement import (
    ALIGNMENT_REFINEMENT_PATH,
    AlignmentOnsetRefinement,
)
from rocksmith_cdlc_generator.fret_mapping import BassMapping, MappedNote, write_bass_mapping
from rocksmith_cdlc_generator.fretboard import E_STANDARD
from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTrack,
)


def _write_current_bass_mapping(project: Path) -> None:
    write_bass_mapping(
        BassMapping(
            tuning=E_STANDARD,
            max_fret=24,
            notes=[MappedNote(start=0.0, duration=0.4, midi=40, string=0, fret=12, source_confidence=0.9, mapping_confidence=0.9)],
        ),
        project / "charts" / "bass_mapped.json",
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


def _write_current_alignment_refinements(project: Path, *, source_sha256: str, track_index: int = 0) -> None:
    """Simulate `align_project_source` having already run both refinement passes.

    Both passes always persist an evidence record, even when they decline to move the
    clock, so a genuinely up-to-date alignment always has both files present at the
    current algorithm version (#431 regression coverage).
    """

    AlignmentOnsetRefinement(
        source_sha256=source_sha256,
        track_index=track_index,
        applied=False,
        shift_seconds=0.0,
        baseline_match_count=0,
        refined_match_count=0,
        candidate_count=0,
        reason="fixture",
    ).write_json(project / ALIGNMENT_REFINEMENT_PATH)
    LeadingRestAlignmentRefinement(
        source_sha256=source_sha256,
        track_index=track_index,
        leading_rest_seconds=0.0,
        applied=False,
        shift_seconds=0.0,
        baseline_onset_matches=0,
        refined_onset_matches=0,
        baseline_pitch_matches=0,
        refined_pitch_matches=0,
        candidate_count=0,
        reason="fixture",
    ).write_json(project / LEADING_REST_REFINEMENT_PATH)


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
    _write_current_alignment_refinements(project, source_sha256="b" * 64)
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


def test_stale_alignment_refinement_reopens_align_tab_step(tmp_path: Path, monkeypatch) -> None:
    """An alignment written before onset/leading-rest refinement must not read as complete.

    Regression coverage for Product Reality #431: packaged retests kept reproducing the
    identical residual late-timing defect after refinement algorithm fixes (#432, #436)
    were merged, because `align-tab` was considered "complete" the moment `alignment.json`
    existed, regardless of whether the current onset/leading-rest refinement algorithms had
    actually run against it. `refinement_is_current`/`leading_rest_refinement_is_current`
    already existed to detect exactly this staleness but were never consulted by the
    planner, so "Run Safe Automatic Steps" never re-ran alignment and the improved
    refinement code never executed on an already-aligned project.
    """

    project = tmp_path / "song"
    (project / "analysis").mkdir(parents=True)
    (project / "analysis" / "bass_raw.json").write_text("{}", encoding="utf-8")
    source = _write_imported_source(project, "sources/imported/song.json", source_sha256="a" * 64, track_index=0)
    _write_alignment(
        project,
        project / "sources/imported/song.json",
        source_sha256="a" * 64,
    )
    # No refinement evidence written: simulates an alignment produced before the
    # onset/leading-rest refinement passes existed (or before their version bump).
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
    assert align.command and "align-source" in align.command and "song.json" in align.command
    assert "431" in align.reason
    assert reconcile.status == "blocked"
    assert reconcile.command is None


def test_partially_stale_alignment_refinement_also_reopens_align_tab_step(tmp_path: Path, monkeypatch) -> None:
    """Only one refinement pass having run is still stale (both must be current)."""

    project = tmp_path / "song"
    (project / "analysis").mkdir(parents=True)
    (project / "analysis" / "bass_raw.json").write_text("{}", encoding="utf-8")
    source = _write_imported_source(project, "sources/imported/song.json", source_sha256="a" * 64, track_index=0)
    _write_alignment(
        project,
        project / "sources/imported/song.json",
        source_sha256="a" * 64,
    )
    # Only the onset-refinement record exists, e.g. from a build that predates the
    # leading-rest refinement pass (#436) entirely.
    AlignmentOnsetRefinement(
        source_sha256="a" * 64,
        track_index=0,
        applied=False,
        shift_seconds=0.0,
        baseline_match_count=0,
        refined_match_count=0,
        candidate_count=0,
        reason="fixture",
    ).write_json(project / ALIGNMENT_REFINEMENT_PATH)
    monkeypatch.setattr(
        workflow_plan,
        "build_project_source_inventory",
        lambda _: _inventory(project, local_sources=[source]),
    )

    plan = workflow_plan.build_project_workflow_plan(project)

    align = next(step for step in plan.steps if step.step_id == "align-tab")
    assert align.status == "ready"
    assert align.command and "align-source" in align.command


def test_current_alignment_refinements_keep_align_tab_complete(tmp_path: Path, monkeypatch) -> None:
    """Sanity check: once both refinement records match, align-tab is complete again."""

    project = tmp_path / "song"
    (project / "analysis").mkdir(parents=True)
    (project / "analysis" / "bass_raw.json").write_text("{}", encoding="utf-8")
    source = _write_imported_source(project, "sources/imported/song.json", source_sha256="a" * 64, track_index=0)
    _write_alignment(
        project,
        project / "sources/imported/song.json",
        source_sha256="a" * 64,
    )
    _write_current_alignment_refinements(project, source_sha256="a" * 64)
    monkeypatch.setattr(
        workflow_plan,
        "build_project_source_inventory",
        lambda _: _inventory(project, local_sources=[source]),
    )

    plan = workflow_plan.build_project_workflow_plan(project)

    align = next(step for step in plan.steps if step.step_id == "align-tab")
    reconcile = next(step for step in plan.steps if step.step_id == "reconcile-tab")
    assert align.status == "complete"
    assert reconcile.status == "ready"


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
        "review/validation_report.json",
    ]:
        path = project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
    _write_current_bass_mapping(project)
    monkeypatch.setattr(workflow_plan, "build_project_source_inventory", lambda _: _inventory(project))

    plan = workflow_plan.build_project_workflow_plan(project)

    map_bass = next(step for step in plan.steps if step.step_id == "map-bass")
    review = next(step for step in plan.steps if step.step_id == "human-review")
    assert map_bass.status == "complete"
    assert review.status == "ready"
    assert review.mode == "human"
    assert plan.next_step_id == "human-review"


def test_stale_bass_mapping_reopens_map_bass_step(tmp_path: Path, monkeypatch) -> None:
    """A mapping written before mapping_algorithm_version existed must not read as complete.

    Regression coverage for the #304 Product Reality finding: an app upgrade that changes
    the Bass mapping algorithm left `charts/bass_mapped.json` on disk from the old
    algorithm, and the planner treated that file's mere existence as "mapping complete",
    so validation kept surfacing failures from stale mapped content and offered no path
    back to re-mapping.
    """

    project = tmp_path / "song"
    for relative in [
        "audio/normalized.wav",
        "analysis/tempo_map.json",
        "analysis/bass_raw.json",
        "review/validation_report.json",
    ]:
        path = project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
    # Simulate a mapping produced before `mapping_algorithm_version` existed on disk.
    legacy_mapping = BassMapping(
        tuning=E_STANDARD,
        max_fret=24,
        notes=[MappedNote(start=0.0, duration=0.4, midi=40, string=0, fret=12, source_confidence=0.9, mapping_confidence=0.9)],
    ).model_dump(mode="json")
    del legacy_mapping["mapping_algorithm_version"]
    mapping_path = project / "charts" / "bass_mapped.json"
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    mapping_path.write_text(json.dumps(legacy_mapping), encoding="utf-8")
    monkeypatch.setattr(workflow_plan, "build_project_source_inventory", lambda _: _inventory(project))

    plan = workflow_plan.build_project_workflow_plan(project)

    map_bass = next(step for step in plan.steps if step.step_id == "map-bass")
    assert map_bass.status == "ready"
    assert map_bass.command and "map-bass" in map_bass.command
    assert "older mapping algorithm" in map_bass.reason
    assert plan.next_step_id == "map-bass"
