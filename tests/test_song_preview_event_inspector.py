from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.song_preview import (
    PreviewArrangement,
    PreviewNoteEvent,
    SongPreviewSnapshot,
)
from rocksmith_cdlc_generator.song_preview_event_inspector import (
    build_preview_event_selection,
)
from rocksmith_cdlc_generator.source_import import SourceTrustClass


def _note(
    event_index: int,
    start_seconds: float,
    *,
    review_required: bool = False,
) -> PreviewNoteEvent:
    return PreviewNoteEvent(
        event_index=event_index,
        start_seconds=start_seconds,
        duration_seconds=0.25,
        midi=64 + event_index,
        note_name="E4",
        string_index=event_index % 6,
        fret=event_index,
        techniques=["accent"],
        import_confidence=0.8,
        trust_class=SourceTrustClass.symbolic_unverified,
        review_required=review_required,
    )


def _arrangement(
    instrument: str,
    notes: list[PreviewNoteEvent],
) -> PreviewArrangement:
    return PreviewArrangement(
        instrument=instrument,
        part_index={"lead": 0, "rhythm": 1, "bass": 2}[instrument],
        part_id={"lead": "P1", "rhythm": "P2", "bass": "P3"}[instrument],
        part_name={"lead": "Lead Guitar", "rhythm": "Rhythm Guitar", "bass": "Bass"}[instrument],
        tuning_midi=[40, 45, 50, 55, 59, 64] if instrument != "bass" else [28, 33, 38, 43],
        output_json=f"sources/imported/{instrument}.json",
        note_count=len(notes),
        notes=notes,
    )


def _snapshot() -> SongPreviewSnapshot:
    return SongPreviewSnapshot(
        source_filename="song.musicxml",
        source_sha256="a" * 64,
        arrangements=[
            _arrangement(
                "lead",
                [
                    _note(2, 2.0),
                    _note(0, 1.0),
                    _note(1, 1.5, review_required=True),
                ],
            ),
            _arrangement("bass", [_note(0, 0.75)]),
        ],
    )


def test_selects_event_with_arrangement_and_source_provenance() -> None:
    state = build_preview_event_selection(_snapshot(), "lead", 1)

    assert state.selection_id == "lead:1"
    assert state.review_id == "lead:1"
    assert state.source_filename == "song.musicxml"
    assert state.source_sha256 == "a" * 64
    assert state.part_id == "P1"
    assert state.part_name == "Lead Guitar"
    assert state.tuning_midi == [40, 45, 50, 55, 59, 64]
    assert state.selected.event_index == 1
    assert state.selected.start_seconds == 1.5


def test_neighbors_are_chronological_even_when_snapshot_notes_are_unsorted() -> None:
    state = build_preview_event_selection(_snapshot(), "lead", 1)

    assert state.previous_event is not None
    assert state.previous_event.event_index == 0
    assert state.next_event is not None
    assert state.next_event.event_index == 2


def test_selection_returns_deep_copies() -> None:
    snapshot = _snapshot()
    state = build_preview_event_selection(snapshot, "lead", 1)

    state.selected.techniques.append("preview-only")
    assert snapshot.arrangements[0].notes[2].techniques == ["accent"]

    assert state.previous_event is not None
    state.previous_event.techniques.append("preview-only")
    assert snapshot.arrangements[0].notes[1].techniques == ["accent"]


def test_non_review_event_has_no_review_id() -> None:
    state = build_preview_event_selection(_snapshot(), "lead", 0)

    assert state.review_id is None


def test_rejects_missing_duplicate_and_invalid_selection_contracts() -> None:
    snapshot = _snapshot()

    with pytest.raises(ValueError, match="non-negative"):
        build_preview_event_selection(snapshot, "lead", -1)
    with pytest.raises(ValueError, match="event not found"):
        build_preview_event_selection(snapshot, "lead", 99)
    with pytest.raises(ValueError, match="arrangement not found"):
        build_preview_event_selection(snapshot, "rhythm", 0)

    duplicate_role = _snapshot()
    duplicate_role.arrangements.append(_arrangement("lead", [_note(3, 3.0)]))
    with pytest.raises(ValueError, match="duplicate arrangement role"):
        build_preview_event_selection(duplicate_role, "lead", 1)

    duplicate_event = _snapshot()
    duplicate_event.arrangements[0].notes.append(_note(1, 9.0))
    with pytest.raises(ValueError, match="duplicate event indices"):
        build_preview_event_selection(duplicate_event, "lead", 1)
