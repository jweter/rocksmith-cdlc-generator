from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import rocksmith_cdlc_generator.workflow_plan as workflow_plan
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.score_fanout import ScoreFanoutEntry, ScoreFanoutManifest
from rocksmith_cdlc_generator.score_source import (
    ArrangementRole,
    ProjectScoreSource,
    ScoreArrangementMapping,
    ScoreTrackCandidate,
)
from rocksmith_cdlc_generator.source_import import ImportedSource, SourceProvenance, SourceTrack


def _score_project(tmp_path: Path, *, confirmed: bool) -> tuple[Path, ProjectScoreSource, SimpleNamespace]:
    project = tmp_path / "song"
    project.mkdir()
    (project / "project.json").write_text("{}", encoding="utf-8")
    stored = project / "sources" / "score" / "original" / "song.gp5"
    stored.parent.mkdir(parents=True)
    stored.write_bytes(b"complete-score")
    digest = sha256_file(stored)
    score = ProjectScoreSource(
        source_filename="song.gp5",
        source_sha256=digest,
        source_format="gp5",
        imported_relative_path=stored.relative_to(project).as_posix(),
        tracks=[
            ScoreTrackCandidate(source_track_index=0, name="Lead", note_count=100),
            ScoreTrackCandidate(source_track_index=1, name="Rhythm", note_count=100),
        ],
        arrangement_mappings=[
            ScoreArrangementMapping(
                role=ArrangementRole.lead,
                source_track_index=0,
                confidence=0.95,
                human_confirmed=confirmed,
            ),
            ScoreArrangementMapping(
                role=ArrangementRole.rhythm,
                source_track_index=1,
                confidence=0.90,
                human_confirmed=confirmed,
            ),
        ],
    )
    score.write_json(project / "sources" / "score" / "source.json")
    receipt = SimpleNamespace(
        family="notation",
        parser_pending=True,
        output_relative_path=None,
        route_action="register_score_source",
        source_sha256=digest,
        human_rights_review_required=False,
    )
    return project, score, receipt


def _inventory(project: Path, receipt: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(
        project_path=str(project),
        local_sources=[receipt],
        local_audio_sources=1,
        unresolved_rights_reviews=0,
        reference_count=0,
        selected_reference=False,
        reviewed_recording_context=False,
    )


def _write_fanout_output(project: Path, score: ProjectScoreSource, mapping: ScoreArrangementMapping) -> str:
    relative = f"sources/imported/shared-{mapping.role.value}.json"
    ImportedSource(
        provenance=SourceProvenance(
            source_type="gp5",
            source_filename=score.source_filename,
            source_sha256=score.source_sha256,
            importer="test",
            importer_version="1",
        ),
        tracks=[
            SourceTrack(
                source_track_index=mapping.source_track_index,
                instrument=mapping.role.value,
                notes=[],
            )
        ],
    ).write_json(project / relative)
    return relative


def test_registered_score_blocks_on_unconfirmed_role_mappings(tmp_path: Path, monkeypatch) -> None:
    project, _, receipt = _score_project(tmp_path, confirmed=False)
    monkeypatch.setattr(
        workflow_plan,
        "build_project_source_inventory",
        lambda _: _inventory(project, receipt),
    )

    plan = workflow_plan.build_project_workflow_plan(project)
    step = next(step for step in plan.steps if step.step_id == "score-arrangements")

    assert step.status == "blocked"
    assert step.mode == "human"
    assert step.command and "cdlc-score-map" in step.command
    assert "lead" in step.reason and "rhythm" in step.reason


def test_confirmed_reviewed_score_is_ready_for_automatic_fanout(tmp_path: Path, monkeypatch) -> None:
    project, _, receipt = _score_project(tmp_path, confirmed=True)
    monkeypatch.setattr(
        workflow_plan,
        "build_project_source_inventory",
        lambda _: _inventory(project, receipt),
    )

    plan = workflow_plan.build_project_workflow_plan(project)
    step = next(step for step in plan.steps if step.step_id == "score-arrangements")

    assert step.status == "ready"
    assert step.mode == "automatic"
    assert step.command == f'cdlc-score-fanout "{project}"'


def test_current_authoritative_fanout_is_complete(tmp_path: Path, monkeypatch) -> None:
    project, score, receipt = _score_project(tmp_path, confirmed=True)
    entries: list[ScoreFanoutEntry] = []
    for mapping in score.arrangement_mappings:
        entries.append(
            ScoreFanoutEntry(
                role=mapping.role,
                source_track_index=mapping.source_track_index,
                output_json=_write_fanout_output(project, score, mapping),
            )
        )
    manifest = ScoreFanoutManifest(
        score_source_sha256=score.source_sha256,
        score_source_format=score.source_format,
        arrangements=entries,
    )
    manifest_path = (
        project / "sources" / "imported" / f"score-fanout-{score.source_sha256[:12]}.json"
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    monkeypatch.setattr(
        workflow_plan,
        "build_project_source_inventory",
        lambda _: _inventory(project, receipt),
    )

    plan = workflow_plan.build_project_workflow_plan(project)
    step = next(step for step in plan.steps if step.step_id == "score-arrangements")

    assert step.status == "complete"
    assert step.command is None
    assert "lead" in step.reason and "rhythm" in step.reason


def test_missing_fanout_output_makes_score_fanout_ready_again(tmp_path: Path, monkeypatch) -> None:
    project, score, receipt = _score_project(tmp_path, confirmed=True)
    mapping = score.arrangement_mappings[0]
    manifest = ScoreFanoutManifest(
        score_source_sha256=score.source_sha256,
        score_source_format=score.source_format,
        arrangements=[
            ScoreFanoutEntry(
                role=mapping.role,
                source_track_index=mapping.source_track_index,
                output_json="sources/imported/missing.json",
            )
        ],
    )
    manifest_path = (
        project / "sources" / "imported" / f"score-fanout-{score.source_sha256[:12]}.json"
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    monkeypatch.setattr(
        workflow_plan,
        "build_project_source_inventory",
        lambda _: _inventory(project, receipt),
    )

    plan = workflow_plan.build_project_workflow_plan(project)
    step = next(step for step in plan.steps if step.step_id == "score-arrangements")

    assert step.status == "ready"
    assert step.command and "cdlc-score-fanout" in step.command
