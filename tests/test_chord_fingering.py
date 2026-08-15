from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import rocksmith_cdlc_generator.chord_fingering as chord_fingering
from rocksmith_cdlc_generator.chord_fingering import ChordFingeringNote
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.song_preview import PreviewArrangement, PreviewNoteEvent, SongPreviewSnapshot
from rocksmith_cdlc_generator.source_import import SourceNoteEvent, SourceTrustClass


def _preview() -> SongPreviewSnapshot:
    notes = [
        PreviewNoteEvent(
            event_index=0,
            start_seconds=2.0,
            duration_seconds=0.5,
            midi=43,
            string_index=0,
            fret=3,
            import_confidence=1.0,
            trust_class=SourceTrustClass.symbolic_verified,
            review_required=False,
        ),
        PreviewNoteEvent(
            event_index=1,
            start_seconds=2.0005,
            duration_seconds=0.5,
            midi=47,
            string_index=1,
            fret=2,
            import_confidence=1.0,
            trust_class=SourceTrustClass.symbolic_verified,
            review_required=False,
        ),
        PreviewNoteEvent(
            event_index=2,
            start_seconds=3.0,
            duration_seconds=0.5,
            midi=50,
            string_index=2,
            fret=0,
            import_confidence=1.0,
            trust_class=SourceTrustClass.symbolic_verified,
            review_required=False,
        ),
    ]
    return SongPreviewSnapshot(
        source_filename="song.gp5",
        source_sha256="1" * 64,
        arrangements=[
            PreviewArrangement(
                instrument="lead",
                part_index=2,
                part_id="track-2",
                part_name="Lead",
                tuning_midi=[40, 45, 50, 55, 59, 64],
                output_json="sources/imported/lead.json",
                note_count=len(notes),
                notes=notes,
            )
        ],
    )


def test_chord_candidate_groups_only_simultaneous_events() -> None:
    candidate = chord_fingering.chord_candidate_for_event(
        _preview(), arrangement="lead", event_index=1
    )
    assert candidate is not None
    assert candidate.event_indices == [0, 1]
    assert candidate.source_track_index == 2
    assert chord_fingering.chord_candidate_for_event(
        _preview(), arrangement="lead", event_index=2
    ) is None


def test_chord_fingering_rejects_duplicate_strings_before_writing(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="multiple notes on one string"):
        chord_fingering.accept_chord_fingering(
            tmp_path,
            arrangement="lead",
            notes=[
                ChordFingeringNote(event_index=0, string_index=0, fret=3),
                ChordFingeringNote(event_index=1, string_index=0, fret=7),
            ],
        )


def test_chord_fingering_acceptance_writes_both_positions_atomically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "song"
    project.mkdir()
    fanout = project / "sources" / "imported" / "score-fanout.json"
    fanout.parent.mkdir(parents=True)
    fanout.write_text("fanout-authority\n", encoding="utf-8")

    tuning = [40, 45, 50, 55, 59, 64]
    source_notes = {
        0: SourceNoteEvent(
            start_seconds=1.0,
            duration_seconds=0.5,
            midi=43,
            string_index=0,
            fret=3,
            import_confidence=1.0,
            trust_class=SourceTrustClass.symbolic_verified,
        ),
        1: SourceNoteEvent(
            start_seconds=1.0005,
            duration_seconds=0.5,
            midi=47,
            string_index=1,
            fret=2,
            import_confidence=1.0,
            trust_class=SourceTrustClass.symbolic_verified,
        ),
    }
    entry = SimpleNamespace(source_track_index=2)
    track = SimpleNamespace(tuning_midi=tuning)
    score = SimpleNamespace(source_sha256="1" * 64, source_format="gp5")

    monkeypatch.setattr(chord_fingering, "_current_fanout", lambda _project: (fanout, object()))
    monkeypatch.setattr(chord_fingering, "load_score_for_mapping_review", lambda _project: score)
    monkeypatch.setattr(chord_fingering, "load_current_reviewed_positions", lambda _project: None)
    monkeypatch.setattr(
        chord_fingering,
        "_source_event",
        lambda _project, arrangement, event_index: (entry, track, source_notes[event_index]),
    )

    layer = chord_fingering.accept_chord_fingering(
        project,
        arrangement="lead",
        notes=[
            ChordFingeringNote(event_index=0, string_index=0, fret=3),
            ChordFingeringNote(event_index=1, string_index=1, fret=2),
        ],
    )

    first = layer.decision_for("lead", 2, 0)
    second = layer.decision_for("lead", 2, 1)
    assert first is not None and (first.string_index, first.fret) == (0, 3)
    assert second is not None and (second.string_index, second.fret) == (1, 2)
    assert first.accepted_at == second.accepted_at
    assert layer.fanout_manifest_sha256 == sha256_file(fanout)
    assert (project / chord_fingering.POSITION_REVIEW_PATH).is_file()


def test_chord_fingering_rejects_non_simultaneous_source_events(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "song"
    project.mkdir()
    fanout = project / "fanout.json"
    fanout.write_text("authority\n", encoding="utf-8")
    entry = SimpleNamespace(source_track_index=2)
    track = SimpleNamespace(tuning_midi=[40, 45, 50, 55, 59, 64])
    notes = {
        0: SimpleNamespace(start_seconds=1.0, midi=43),
        1: SimpleNamespace(start_seconds=1.02, midi=47),
    }
    monkeypatch.setattr(chord_fingering, "_current_fanout", lambda _project: (fanout, object()))
    monkeypatch.setattr(
        chord_fingering,
        "load_score_for_mapping_review",
        lambda _project: SimpleNamespace(source_sha256="1" * 64, source_format="gp5"),
    )
    monkeypatch.setattr(chord_fingering, "load_current_reviewed_positions", lambda _project: None)
    monkeypatch.setattr(
        chord_fingering,
        "_source_event",
        lambda _project, arrangement, event_index: (entry, track, notes[event_index]),
    )

    with pytest.raises(ValueError, match="not one simultaneous source chord"):
        chord_fingering.accept_chord_fingering(
            project,
            arrangement="lead",
            notes=[
                ChordFingeringNote(event_index=0, string_index=0, fret=3),
                ChordFingeringNote(event_index=1, string_index=1, fret=2),
            ],
        )
