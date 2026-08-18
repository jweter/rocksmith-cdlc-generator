from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

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
    SourceTrustClass,
)
from rocksmith_cdlc_generator.source_track_trust_review import record_track_source_trust_acceptance
from rocksmith_cdlc_generator.track_trust_projection import apply_current_track_source_trust


def _write_project(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "song"
    project.mkdir()
    (project / "project.json").write_text("{}\n", encoding="utf-8")

    score_file = project / "sources" / "score" / "original" / "song.gp5"
    score_file.parent.mkdir(parents=True, exist_ok=True)
    score_file.write_bytes(b"score")
    score_sha = hashlib.sha256(score_file.read_bytes()).hexdigest()

    ProjectScoreSource(
        source_filename="song.gp5",
        source_sha256=score_sha,
        source_format="gp5",
        imported_relative_path="sources/score/original/song.gp5",
        tracks=[
            ScoreTrackCandidate(
                source_track_index=2,
                name="Lead",
                instrument_hint="lead",
                tuning_midi=[40, 45, 50, 55, 59, 64],
                note_count=2,
            )
        ],
        arrangement_mappings=[
            ScoreArrangementMapping(
                role=ArrangementRole.lead,
                source_track_index=2,
                confidence=1.0,
                human_confirmed=True,
            )
        ],
    ).write_json(project / "sources" / "score" / "source.json")

    output = project / "sources" / "imported" / "score-lead.json"
    ImportedSource(
        provenance=SourceProvenance(
            source_type="gp5",
            source_filename="song.gp5",
            source_sha256=score_sha,
            importer="test",
            importer_version="1",
        ),
        tracks=[
            SourceTrack(
                source_track_index=2,
                name="Lead",
                instrument="lead",
                tuning_midi=[40, 45, 50, 55, 59, 64],
                notes=[
                    SourceNoteEvent(
                        start_seconds=1.0,
                        duration_seconds=0.5,
                        midi=43,
                        string_index=0,
                        fret=3,
                        import_confidence=1.0,
                        trust_class=SourceTrustClass.symbolic_unverified,
                    ),
                    SourceNoteEvent(
                        start_seconds=2.0,
                        duration_seconds=0.5,
                        midi=47,
                        string_index=1,
                        fret=2,
                        techniques=["tie", "accent"],
                        import_confidence=1.0,
                        trust_class=SourceTrustClass.symbolic_verified,
                        review_required=True,
                    ),
                ],
            )
        ],
    ).write_json(output)

    manifest = project / "sources" / "imported" / f"score-fanout-{score_sha[:12]}.json"
    manifest.write_text(
        ScoreFanoutManifest(
            score_source_sha256=score_sha,
            score_source_format="gp5",
            arrangements=[
                ScoreFanoutEntry(
                    role=ArrangementRole.lead,
                    source_track_index=2,
                    output_json=output.relative_to(project).as_posix(),
                )
            ],
        ).model_dump_json(indent=2)
        + "\n",
        encoding="utf-8",
    )
    return project, output


def test_current_acceptance_projects_user_confirmed_without_clearing_review(tmp_path: Path) -> None:
    project, output = _write_project(tmp_path)
    persisted_before = output.read_bytes()
    record_track_source_trust_acceptance(project, arrangement="lead")

    projected, applied = apply_current_track_source_trust(
        project,
        ImportedSource.read_json(output),
        arrangement="lead",
        source_track_index=2,
    )

    assert applied is True
    assert [note.trust_class for note in projected.tracks[0].notes] == [
        SourceTrustClass.user_confirmed,
        SourceTrustClass.user_confirmed,
    ]
    assert projected.tracks[0].notes[1].review_required is True
    assert projected.tracks[0].notes[1].techniques == ["tie", "accent"]
    assert output.read_bytes() == persisted_before
    assert ImportedSource.read_json(output).tracks[0].notes[0].trust_class is SourceTrustClass.symbolic_unverified


def test_without_acceptance_returns_copied_source_unchanged(tmp_path: Path) -> None:
    project, output = _write_project(tmp_path)
    source = ImportedSource.read_json(output)

    projected, applied = apply_current_track_source_trust(
        project,
        source,
        arrangement="lead",
        source_track_index=2,
    )

    assert applied is False
    assert projected == source
    assert projected is not source


def test_projection_rejects_non_current_input_after_acceptance(tmp_path: Path) -> None:
    project, output = _write_project(tmp_path)
    record_track_source_trust_acceptance(project, arrangement="lead")
    source = ImportedSource.read_json(output)
    source.tracks[0].notes[0].duration_seconds = 0.75

    with pytest.raises(ValueError, match="does not match accepted fan-out content"):
        apply_current_track_source_trust(
            project,
            source,
            arrangement="lead",
            source_track_index=2,
        )
