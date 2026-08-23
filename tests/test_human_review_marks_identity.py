from __future__ import annotations

from pathlib import Path

from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.human_review_marks import (
    current_marks_for_arrangement,
    load_current_human_review_layer,
    mark_event,
)
from rocksmith_cdlc_generator.score_fanout import ScoreFanoutEntry, ScoreFanoutManifest
from rocksmith_cdlc_generator.score_source import (
    ArrangementRole,
    ProjectScoreSource,
    ScoreArrangementMapping,
    ScoreTrackCandidate,
)
from rocksmith_cdlc_generator.source_import import ImportedSource, SourceNoteEvent, SourceProvenance, SourceTrack


def _write_registered_score(project: Path, *, tracks: list[ScoreTrackCandidate], mappings: list[ScoreArrangementMapping]) -> str:
    project.mkdir(parents=True, exist_ok=True)
    (project / "project.json").write_text("{}", encoding="utf-8")
    stored = project / "sources" / "score" / "original" / "song.gp5"
    stored.parent.mkdir(parents=True, exist_ok=True)
    stored.write_bytes(b"complete-score")
    digest = sha256_file(stored)
    score = ProjectScoreSource(
        source_filename="song.gp5",
        source_sha256=digest,
        source_format="gp5",
        imported_relative_path=stored.relative_to(project).as_posix(),
        tracks=tracks,
        arrangement_mappings=mappings,
    )
    (project / "sources" / "score").mkdir(parents=True, exist_ok=True)
    score.write_json(project / "sources" / "score" / "source.json")
    return digest


def _write_fanout(
    project: Path,
    *,
    digest: str,
    role: ArrangementRole,
    source_track_index: int,
    notes: list[SourceNoteEvent],
    output_name: str,
) -> Path:
    output = project / "sources" / "imported" / f"{output_name}.json"
    ImportedSource(
        provenance=SourceProvenance(
            source_type="gp5", source_filename="song.gp5", source_sha256=digest, importer="test", importer_version="1"
        ),
        tracks=[SourceTrack(source_track_index=source_track_index, instrument=role.value, notes=notes)],
    ).write_json(output)
    manifest = ScoreFanoutManifest(
        score_source_sha256=digest,
        score_source_format="gp5",
        arrangements=[
            ScoreFanoutEntry(role=role, source_track_index=source_track_index, output_json=output.relative_to(project).as_posix())
        ],
    )
    manifest_path = project / "sources" / "imported" / f"score-fanout-{digest[:12]}.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return output


def _note(midi: int, start: float) -> SourceNoteEvent:
    return SourceNoteEvent(start_seconds=start, duration_seconds=0.4, midi=midi, import_confidence=0.9)


def test_remapping_to_a_different_track_invalidates_stale_mark_without_changing_score_sha(tmp_path: Path) -> None:
    """#2: a confirmed role-mapping change replaces which notes populate an arrangement's
    event indices without changing the registered score's own SHA256. A mark set before
    the remap must not keep loading as current afterward and silently attach to a
    different, unrelated event."""

    project = tmp_path / "project"
    tracks = [
        ScoreTrackCandidate(source_track_index=0, name="Lead A", note_count=1),
        ScoreTrackCandidate(source_track_index=1, name="Lead B", note_count=1),
    ]
    mappings = [ScoreArrangementMapping(role=ArrangementRole.lead, source_track_index=0, confidence=1.0, human_confirmed=True)]
    digest = _write_registered_score(project, tracks=tracks, mappings=mappings)

    # Original mapping: track 0, one note at MIDI 40 / t=0.0.
    _write_fanout(project, digest=digest, role=ArrangementRole.lead, source_track_index=0, notes=[_note(40, 0.0)], output_name="lead")

    mark_event(
        project,
        source_sha256=digest,
        arrangement="lead",
        event_index=0,
        source_start_seconds=0.0,
        midi=40,
        string_index=0,
        fret=0,
        state="wrong",
    )
    assert load_current_human_review_layer(project, digest) is not None
    assert len(current_marks_for_arrangement(project, digest, "lead")) == 1

    # Human remaps Lead to track 1 (a totally different note stream), same score SHA256.
    # This mirrors confirm_score_mapping deleting only the fan-out manifest for the same
    # score, then a fresh fan-out being published for the new mapping.
    manifest_path = project / "sources" / "imported" / f"score-fanout-{digest[:12]}.json"
    manifest_path.unlink()
    _write_fanout(
        project, digest=digest, role=ArrangementRole.lead, source_track_index=1, notes=[_note(52, 3.0)], output_name="lead-remapped"
    )

    # The stale mark must not load as current, and must not silently apply to whatever
    # unrelated event now sits at index 0.
    assert load_current_human_review_layer(project, digest) is None
    assert current_marks_for_arrangement(project, digest, "lead") == []


def test_composed_selection_style_change_is_caught_by_per_event_signature_even_if_manifest_hash_is_unchanged(
    tmp_path: Path,
) -> None:
    """#2 (Lead/Rhythm composed multi-track selection edge case): a composed-track
    selection override is applied downstream of the base fan-out manifest and does not
    itself change the manifest's hash. ``current_marks_for_arrangement`` must still catch
    a note-stream change at a fixed event index by checking the mark's own stored
    (MIDI, onset) against the arrangement's live current event."""

    project = tmp_path / "project"
    tracks = [ScoreTrackCandidate(source_track_index=0, name="Lead", note_count=1)]
    mappings = [ScoreArrangementMapping(role=ArrangementRole.lead, source_track_index=0, confidence=1.0, human_confirmed=True)]
    digest = _write_registered_score(project, tracks=tracks, mappings=mappings)
    output = _write_fanout(
        project, digest=digest, role=ArrangementRole.lead, source_track_index=0, notes=[_note(40, 0.0)], output_name="lead"
    )

    mark_event(
        project,
        source_sha256=digest,
        arrangement="lead",
        event_index=0,
        source_start_seconds=0.0,
        midi=40,
        string_index=0,
        fret=0,
        state="wrong",
    )
    assert len(current_marks_for_arrangement(project, digest, "lead")) == 1

    # Rewrite the fan-out output's note content in place (same file path, same manifest,
    # same manifest hash) -- this is what a downstream composed-selection override would
    # produce for Lead/Rhythm. load_current_human_review_layer's cheap file-identity
    # check alone cannot see this; only the per-event signature check can.
    ImportedSource(
        provenance=SourceProvenance(
            source_type="gp5", source_filename="song.gp5", source_sha256=digest, importer="test", importer_version="1"
        ),
        tracks=[SourceTrack(source_track_index=0, instrument="lead", notes=[_note(67, 5.0)])],
    ).write_json(output)

    # The cheap identity check still reports the layer as "current" (manifest unchanged)...
    assert load_current_human_review_layer(project, digest) is not None
    # ...but the stronger per-event check drops the now-mismatched mark rather than
    # letting it silently apply to the new, unrelated event at the same index.
    assert current_marks_for_arrangement(project, digest, "lead") == []


def test_mark_still_applies_when_nothing_about_the_arrangement_changed(tmp_path: Path) -> None:
    project = tmp_path / "project"
    tracks = [ScoreTrackCandidate(source_track_index=0, name="Bass", note_count=1)]
    mappings = [ScoreArrangementMapping(role=ArrangementRole.bass, source_track_index=0, confidence=1.0, human_confirmed=True)]
    digest = _write_registered_score(project, tracks=tracks, mappings=mappings)
    _write_fanout(project, digest=digest, role=ArrangementRole.bass, source_track_index=0, notes=[_note(28, 1.5)], output_name="bass")

    mark_event(
        project,
        source_sha256=digest,
        arrangement="bass",
        event_index=0,
        source_start_seconds=1.5,
        midi=28,
        string_index=0,
        fret=0,
        state="wrong",
    )
    marks = current_marks_for_arrangement(project, digest, "bass")
    assert len(marks) == 1
    assert marks[0].state == "wrong"
