from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.song_preview import (
    PreviewArrangement,
    PreviewNoteEvent,
    SongPreviewSnapshot,
)
from rocksmith_cdlc_generator.song_preview_playhead import build_preview_playhead_state
from rocksmith_cdlc_generator.source_import import SourceTrustClass


def _note(
    event_index: int,
    start: float,
    duration: float,
    *,
    midi: int = 64,
    review_required: bool = True,
) -> PreviewNoteEvent:
    return PreviewNoteEvent(
        event_index=event_index,
        start_seconds=start,
        duration_seconds=duration,
        midi=midi,
        note_name="E4",
        string_index=0,
        fret=0,
        techniques=["accent"],
        import_confidence=0.75,
        trust_class=SourceTrustClass.symbolic_unverified,
        review_required=review_required,
    )


def _arrangement(instrument: str, notes: list[PreviewNoteEvent]) -> PreviewArrangement:
    return PreviewArrangement(
        instrument=instrument,
        part_index={"lead": 0, "rhythm": 1, "bass": 2}[instrument],
        part_id={"lead": "P1", "rhythm": "P2", "bass": "P3"}[instrument],
        part_name={"lead": "Lead", "rhythm": "Rhythm", "bass": "Bass"}[instrument],
        tuning_midi=[40, 45, 50, 55, 59, 64] if instrument != "bass" else [28, 33, 38, 43],
        output_json=f"sources/imported/{instrument}.json",
        note_count=len(notes),
        notes=notes,
    )


def _snapshot() -> SongPreviewSnapshot:
    return SongPreviewSnapshot(
        source_filename="song.musicxml",
        source_sha256="a" * 64,
        beat_times_seconds=[0.0, 0.5, 1.0, 1.5],
        arrangements=[
            _arrangement(
                "lead",
                [
                    _note(2, 1.2, 0.2),
                    _note(0, 0.4, 0.4),
                    _note(1, 0.5, 0.5, midi=67),
                ],
            ),
            _arrangement("bass", [_note(0, 0.75, 0.5, midi=40)]),
        ],
    )


def test_builds_synchronized_playhead_state() -> None:
    state = build_preview_playhead_state(_snapshot(), 0.6)

    assert state.position_seconds == 0.6
    assert state.previous_beat_seconds == 0.5
    assert state.next_beat_seconds == 1.0
    assert [lane.instrument for lane in state.lanes] == ["lead", "bass"]
    assert [note.event_index for note in state.lanes[0].active_notes] == [0, 1]
    assert state.lanes[0].next_note is not None
    assert state.lanes[0].next_note.event_index == 2
    assert state.lanes[1].active_notes == []
    assert state.lanes[1].next_note is not None
    assert state.lanes[1].next_note.event_index == 0


def test_note_end_is_not_active_at_exact_boundary() -> None:
    state = build_preview_playhead_state(_snapshot(), 0.8)

    assert [note.event_index for note in state.lanes[0].active_notes] == [1]


def test_playhead_projection_does_not_mutate_snapshot() -> None:
    snapshot = _snapshot()
    state = build_preview_playhead_state(snapshot, 0.6)

    state.lanes[0].active_notes[0].techniques.append("preview-only")
    assert snapshot.arrangements[0].notes[1].techniques == ["accent"]

    assert state.lanes[0].tuning_midi is not None
    state.lanes[0].tuning_midi[0] = 99
    assert snapshot.arrangements[0].tuning_midi == [40, 45, 50, 55, 59, 64]


def test_playhead_before_first_and_after_last_beat() -> None:
    snapshot = _snapshot()

    before = build_preview_playhead_state(snapshot, 0.0)
    after = build_preview_playhead_state(snapshot, 2.0)

    assert before.previous_beat_seconds == 0.0
    assert before.next_beat_seconds == 0.5
    assert after.previous_beat_seconds == 1.5
    assert after.next_beat_seconds is None
    assert all(lane.next_note is None for lane in after.lanes)


def test_rejects_negative_playhead_position() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        build_preview_playhead_state(_snapshot(), -0.001)
