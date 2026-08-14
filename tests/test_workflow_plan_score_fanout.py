from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import rocksmith_cdlc_generator.workflow_plan as workflow_plan
from rocksmith_cdlc_generator.score_fanout import ScoreFanoutEntry, ScoreFanoutManifest
from rocksmith_cdlc_generator.score_source import (
    ArrangementRole,
    ProjectScoreSource,
    ScoreArrangementMapping,
    ScoreTrackCandidate,
)
from rocksmith_cdlc_generator.source_import import ImportedSource, SourceProvenance, SourceTrack


def _inventory(project: Path, local_sources: list[SimpleNamespace]) -> SimpleNamespace:
    return SimpleNamespace(
        project_path=str(project),
        local_sources=local_sources,
        local_audio_sources=1,
        unresolved_rights_reviews=0,
        reference_count=0,
        selected_reference=False,
        reviewed_recording_context=False,
    )


def _write_source(
    project: Path,
    relative: str,
    *,
    source_sha256: str,
    instrument: str,
    track_index: int,
) -> Path:
    path = project / relative
    ImportedSource(
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
                notes=[],
            )
        ],
    ).write_json(path)
    return path


def _legacy_receipt(relative: str) -> SimpleNamespace:
    return SimpleNamespace(
        family="notation",
        parser_pending=False,
        output_relative_path=relative,
    )


def _score(*, digest: str, role: ArrangementRole, track_index: int) -> ProjectScoreSource:
    return ProjectScoreSource(
        source_filename="song.gp5",
        source_sha256=digest,
        source_format="gp5",
        imported_relative_path="sources/score/original/song.gp5",
        tracks=[
            ScoreTrackCandidate(
                source_track_index=track_index,
                name=f"{role.value} track",
                note_count=10,
            )
        ],
        arrangement_mappings=[
            ScoreArrangementMapping(
                role=role,
                source_track_index=track_index,
                confidence=1.0,
                human_confirmed=True,
            )
        ],
    )


def _write_fanout(
    project: Path,
    score: ProjectScoreSource,
    *,
    role: ArrangementRole,
    track_index: int,
) -> Path:
    relative = f"sources/imported/fanout-{role.value}.json"
    output = _write_source(
        project,
        relative,
        source_sha256=score.source_sha256,
        instrument=role.value,
        track_index=track_index,
    )
    manifest = ScoreFanoutManifest(
        score_source_sha256=score.source_sha256,
        score_source_format=score.source_format,
        arrangements=[
            ScoreFanoutEntry(
                role=role,
                source_track_index=track_index,
                output_json=relative,
            )
        ],
    )
    destination = (
        project
        / "sources"
        / "imported"
        / f"score-fanout-{score.source_sha256[:12]}.json"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return output


def test_current_shared_score_bass_fanout_outranks_legacy_bass_sources(
    tmp_path: Path, monkeypatch
) -> None:
    project = tmp_path / "song"
    (project / "analysis").mkdir(parents=True)
    (project / "analysis" / "tempo_map.json").write_text("{}", encoding="utf-8")

    legacy_a = "sources/imported/legacy-a.json"
    legacy_b = "sources/imported/legacy-b.json"
    _write_source(project, legacy_a, source_sha256="b" * 64, instrument="bass", track_index=0)
    _write_source(project, legacy_b, source_sha256="c" * 64, instrument="bass", track_index=1)

    score = _score(digest="a" * 64, role=ArrangementRole.bass, track_index=2)
    fanout = _write_fanout(
        project,
        score,
        role=ArrangementRole.bass,
        track_index=2,
    )

    monkeypatch.setattr(
        workflow_plan,
        "build_project_source_inventory",
        lambda _: _inventory(project, [_legacy_receipt(legacy_a), _legacy_receipt(legacy_b)]),
    )
    monkeypatch.setattr(workflow_plan, "_load_registered_score", lambda _: (True, score))
    monkeypatch.setattr(workflow_plan, "_score_rights_are_resolved", lambda *_: True)

    plan = workflow_plan.build_project_workflow_plan(project)

    arrangements = next(step for step in plan.steps if step.step_id == "score-arrangements")
    align = next(step for step in plan.steps if step.step_id == "align-tab")
    assert arrangements.status == "complete"
    assert align.status == "ready"
    assert align.mode == "automatic"
    assert align.command is not None
    assert str(fanout.resolve()) in align.command
    assert "--track-index 2" in align.command
    assert "human-confirmed shared-score Bass arrangement" in align.reason


def test_lead_only_fanout_does_not_hide_legacy_bass_source(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "song"
    (project / "analysis").mkdir(parents=True)
    (project / "analysis" / "tempo_map.json").write_text("{}", encoding="utf-8")

    legacy = "sources/imported/legacy-bass.json"
    legacy_path = _write_source(
        project,
        legacy,
        source_sha256="b" * 64,
        instrument="bass",
        track_index=4,
    )
    score = _score(digest="a" * 64, role=ArrangementRole.lead, track_index=1)
    _write_fanout(project, score, role=ArrangementRole.lead, track_index=1)

    monkeypatch.setattr(
        workflow_plan,
        "build_project_source_inventory",
        lambda _: _inventory(project, [_legacy_receipt(legacy)]),
    )
    monkeypatch.setattr(workflow_plan, "_load_registered_score", lambda _: (True, score))
    monkeypatch.setattr(workflow_plan, "_score_rights_are_resolved", lambda *_: True)

    plan = workflow_plan.build_project_workflow_plan(project)

    align = next(step for step in plan.steps if step.step_id == "align-tab")
    assert align.status == "ready"
    assert align.mode == "automatic"
    assert align.command is not None
    assert str(legacy_path.resolve()) in align.command
    assert "--track-index 4" in align.command
