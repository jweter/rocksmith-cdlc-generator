from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from rocksmith_cdlc_generator.hashing import sha256_file
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
from rocksmith_cdlc_generator.source_track_trust_review import (
    TRACK_SOURCE_TRUST_REVIEW_PATH,
    load_current_track_source_trust_review,
    record_track_source_trust_acceptance,
)


def _write_project(
    tmp_path: Path,
    *,
    human_confirmed: bool = True,
    missing_position: bool = False,
    pitch_conflict: bool = False,
) -> tuple[Path, Path]:
    project = tmp_path / "song"
    project.mkdir()
    (project / "project.json").write_text("{}\n", encoding="utf-8")

    stored_score = project / "sources" / "score" / "original" / "song.gp5"
    stored_score.parent.mkdir(parents=True, exist_ok=True)
    stored_score.write_bytes(b"complete-score")
    score_sha = hashlib.sha256(stored_score.read_bytes()).hexdigest()

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
                human_confirmed=human_confirmed,
            )
        ],
    ).write_json(project / "sources" / "score" / "source.json")

    tuning = [40, 45, 50, 55, 59, 64]
    first_fret = 4 if pitch_conflict else 3
    notes = [
        SourceNoteEvent(
            start_seconds=1.0,
            duration_seconds=0.5,
            midi=43,
            string_index=None if missing_position else 0,
            fret=None if missing_position else first_fret,
            import_confidence=1.0,
            trust_class=SourceTrustClass.symbolic_unverified,
        ),
        SourceNoteEvent(
            start_seconds=2.0,
            duration_seconds=0.5,
            midi=47,
            string_index=1,
            fret=2,
            techniques=["tie"],
            import_confidence=1.0,
            trust_class=SourceTrustClass.symbolic_unverified,
            review_required=True,
        ),
    ]
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
                tuning_midi=tuning,
                notes=notes,
            )
        ],
    ).write_json(output)

    manifest_path = project / "sources" / "imported" / f"score-fanout-{score_sha[:12]}.json"
    manifest_path.write_text(
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


def test_records_exact_track_acceptance_without_mutating_fanout(tmp_path: Path) -> None:
    project, output = _write_project(tmp_path)
    source_hash = sha256_file(output)

    layer = record_track_source_trust_acceptance(project, arrangement="lead")

    assert sha256_file(output) == source_hash
    assert (project / TRACK_SOURCE_TRUST_REVIEW_PATH).is_file()
    assert layer.score_format == "gp5"
    assert len(layer.acceptances) == 1
    acceptance = layer.acceptances[0]
    assert acceptance.arrangement == "lead"
    assert acceptance.source_track_index == 2
    assert acceptance.source_track_name == "Lead"
    assert acceptance.output_sha256 == source_hash
    assert acceptance.note_count == 2
    assert acceptance.accepted_scope == "imported_note_identity_and_positions"
    assert load_current_track_source_trust_review(project) == layer


def test_track_acceptance_does_not_clear_independent_event_review_flags(tmp_path: Path) -> None:
    project, output = _write_project(tmp_path)

    record_track_source_trust_acceptance(project, arrangement="lead")

    imported = ImportedSource.read_json(output)
    assert imported.tracks[0].notes[1].review_required is True
    assert imported.tracks[0].notes[1].techniques == ["tie"]
    assert imported.tracks[0].notes[1].trust_class is SourceTrustClass.symbolic_unverified


def test_rejects_missing_position_instead_of_manufacturing_one(tmp_path: Path) -> None:
    project, _output = _write_project(tmp_path, missing_position=True)

    with pytest.raises(ValueError, match="has no explicit string/fret position"):
        record_track_source_trust_acceptance(project, arrangement="lead")

    assert not (project / TRACK_SOURCE_TRUST_REVIEW_PATH).exists()


def test_rejects_pitch_inconsistent_source_position(tmp_path: Path) -> None:
    project, _output = _write_project(tmp_path, pitch_conflict=True)

    with pytest.raises(ValueError, match="does not produce source MIDI pitch"):
        record_track_source_trust_acceptance(project, arrangement="lead")


def test_rejects_track_when_score_mapping_is_no_longer_human_confirmed(tmp_path: Path) -> None:
    project, _output = _write_project(tmp_path, human_confirmed=False)

    with pytest.raises(ValueError, match="no longer human-confirmed/current"):
        record_track_source_trust_acceptance(project, arrangement="lead")


def test_acceptance_fails_closed_when_fanout_content_changes(tmp_path: Path) -> None:
    project, output = _write_project(tmp_path)
    record_track_source_trust_acceptance(project, arrangement="lead")

    imported = ImportedSource.read_json(output)
    imported.warnings.append("changed after review")
    imported.write_json(output)

    with pytest.raises(ValueError, match="stale for current fan-out content"):
        load_current_track_source_trust_review(project)


def test_acceptance_fails_closed_when_manifest_changes(tmp_path: Path) -> None:
    project, _output = _write_project(tmp_path)
    layer = record_track_source_trust_acceptance(project, arrangement="lead")
    manifest_path = project / layer.fanout_manifest_path
    manifest_path.write_text(manifest_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="stale for the current score fan-out"):
        load_current_track_source_trust_review(project)
