from __future__ import annotations

from rocksmith_cdlc_generator.song_preview import (
    PreviewArrangement,
    PreviewNoteEvent,
    SongPreviewSnapshot,
    build_preview_review_queue,
)
from rocksmith_cdlc_generator.source_import import SourceTrustClass


def _note(
    *,
    event_index: int,
    start_seconds: float,
    confidence: float,
    review_required: bool = True,
) -> PreviewNoteEvent:
    return PreviewNoteEvent(
        event_index=event_index,
        start_seconds=start_seconds,
        duration_seconds=0.25,
        midi=64,
        note_name="E4",
        string_index=0,
        fret=0,
        techniques=["accent"],
        import_confidence=confidence,
        trust_class=SourceTrustClass.symbolic_unverified,
        review_required=review_required,
    )


def _arrangement(instrument: str, notes: list[PreviewNoteEvent]) -> PreviewArrangement:
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


def test_builds_cross_arrangement_review_queue_in_song_order() -> None:
    snapshot = SongPreviewSnapshot(
        source_filename="song.musicxml",
        source_sha256="a" * 64,
        arrangements=[
            _arrangement("lead", [_note(event_index=0, start_seconds=2.0, confidence=0.9)]),
            _arrangement("rhythm", [_note(event_index=0, start_seconds=1.0, confidence=0.8)]),
            _arrangement("bass", [_note(event_index=0, start_seconds=3.0, confidence=0.7)]),
        ],
    )

    queue = build_preview_review_queue(snapshot)

    assert [item.review_id for item in queue.items] == ["rhythm:0", "lead:0", "bass:0"]
    assert [item.start_seconds for item in queue.items] == [1.0, 2.0, 3.0]


def test_same_onset_surfaces_lower_confidence_then_stable_role_order() -> None:
    snapshot = SongPreviewSnapshot(
        source_filename="song.musicxml",
        source_sha256="a" * 64,
        arrangements=[
            _arrangement("lead", [_note(event_index=0, start_seconds=1.0, confidence=0.8)]),
            _arrangement("rhythm", [_note(event_index=0, start_seconds=1.0, confidence=0.8)]),
            _arrangement("bass", [_note(event_index=0, start_seconds=1.0, confidence=0.4)]),
        ],
    )

    queue = build_preview_review_queue(snapshot)

    assert [item.review_id for item in queue.items] == ["bass:0", "lead:0", "rhythm:0"]


def test_queue_omits_confirmed_events_and_copies_mutable_values() -> None:
    review_note = _note(event_index=0, start_seconds=1.0, confidence=0.5)
    confirmed_note = _note(
        event_index=1,
        start_seconds=2.0,
        confidence=1.0,
        review_required=False,
    )
    snapshot = SongPreviewSnapshot(
        source_filename="song.musicxml",
        source_sha256="a" * 64,
        arrangements=[_arrangement("lead", [review_note, confirmed_note])],
    )

    queue = build_preview_review_queue(snapshot)

    assert [item.review_id for item in queue.items] == ["lead:0"]
    queue.items[0].techniques.append("preview-only")
    assert snapshot.arrangements[0].notes[0].techniques == ["accent"]


def test_empty_review_queue_is_valid() -> None:
    snapshot = SongPreviewSnapshot(
        source_filename="song.musicxml",
        source_sha256="a" * 64,
        arrangements=[
            _arrangement(
                "bass",
                [_note(event_index=0, start_seconds=1.0, confidence=1.0, review_required=False)],
            )
        ],
    )

    assert build_preview_review_queue(snapshot).items == []
