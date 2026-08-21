from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.project_fretboard_diagnostics import build_project_fretboard_diagnostic
from rocksmith_cdlc_generator.score_fanout import ScoreFanoutEntry, ScoreFanoutManifest
from rocksmith_cdlc_generator.score_source import (
    ArrangementRole,
    ProjectScoreSource,
    ScoreArrangementMapping,
    ScoreTrackCandidate,
)
from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTrack,
)


def _project(tmp_path: Path, *, confirmed: bool = True) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text("{}", encoding="utf-8")

    stored = project / "sources" / "score" / "original" / "song.gp5"
    stored.parent.mkdir(parents=True)
    stored.write_bytes(b"synthetic-score")
    digest = sha256_file(stored)

    score = ProjectScoreSource(
        source_filename="song.gp5",
        source_sha256=digest,
        source_format="gp5",
        imported_relative_path=stored.relative_to(project).as_posix(),
        tracks=[ScoreTrackCandidate(source_track_index=2, name="Bass", note_count=2)],
        arrangement_mappings=[
            ScoreArrangementMapping(
                role=ArrangementRole.bass,
                source_track_index=2,
                confidence=1.0,
                basis=["test"],
                human_confirmed=confirmed,
            )
        ],
    )
    score.write_json(project / "sources" / "score" / "source.json")

    output = project / "sources" / "imported" / "bass.json"
    ImportedSource(
        provenance=SourceProvenance(
            source_type="gp5",
            source_filename="song.gp5",
            source_sha256=digest,
            importer="test",
            importer_version="1",
        ),
        tracks=[
            SourceTrack(
                source_track_index=2,
                name="Bass",
                instrument="bass",
                tuning_midi=[28, 33, 38, 43],
                notes=[
                    SourceNoteEvent(
                        start_seconds=0.0,
                        duration_seconds=0.5,
                        midi=43,
                        string_index=3,
                        fret=0,
                        import_confidence=1.0,
                    ),
                    SourceNoteEvent(
                        start_seconds=0.5,
                        duration_seconds=0.5,
                        midi=45,
                        string_index=None,
                        fret=None,
                        import_confidence=1.0,
                    ),
                ],
            )
        ],
    ).write_json(output)

    manifest = ScoreFanoutManifest(
        score_source_sha256=digest,
        score_source_format="gp5",
        arrangements=[
            ScoreFanoutEntry(
                role=ArrangementRole.bass,
                source_track_index=2,
                output_json=output.relative_to(project).as_posix(),
            )
        ],
    )
    manifest_path = project / "sources" / "imported" / f"score-fanout-{digest[:12]}.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return project


def test_builds_project_bound_bass_position_diagnostic(tmp_path: Path) -> None:
    diagnostic = build_project_fretboard_diagnostic(_project(tmp_path), arrangement="bass")

    assert diagnostic.arrangement is ArrangementRole.bass
    assert diagnostic.source_track_index == 2
    assert diagnostic.inventory.source_position_match_count == 1
    assert diagnostic.inventory.missing_source_position_count == 1
    assert diagnostic.inventory.inconsistent_source_position_count == 0
    assert diagnostic.inventory.ambiguous_event_count == 2
    assert diagnostic.model_dump()["inventory"]["events"][1]["source_position_status"] == "missing"


def test_rejects_unconfirmed_role_before_using_fanout(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="bass score mapping is not human-confirmed"):
        build_project_fretboard_diagnostic(_project(tmp_path, confirmed=False), arrangement="bass")
