from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.song_preview import (
    PreviewArrangement,
    PreviewNoteEvent,
    SongPreviewSnapshot,
)
from rocksmith_cdlc_generator.song_preview_workspace import build_preview_workspace_state
from rocksmith_cdlc_generator.source_import import (
    SourceTempoEvent,
    SourceTimeSignatureEvent,
    SourceTrustClass,
)


def _note(
    *,
    event_index: int,
    start_seconds: float,
    review_required: bool,
) -> PreviewNoteEvent:
    return PreviewNoteEvent(
        event_index=event_index,
        start_seconds=start_seconds,
        duration_seconds=0.2,
        midi=64,
        note_name="E4",
        string_index=0,
        fret=0,
        techniques=["accent"],
        import_confidence=0.9 if not review_required else 0.5,
        trust_class=SourceTrustClass.symbolic_unverified,
        review_required=review_required,
    )


def _snapshot(*, include_review: bool = True) -> SongPreviewSnapshot:
    notes = [
        _note(event_index=0, start_seconds=0.45, review_required=False),
        _note(event_index=1, start_seconds=0.8, review_required=include_review),
    ]
    return SongPreviewSnapshot(
        source_filename="song.musicxml",
        source_sha256="a" * 64,
        beat_times_seconds=[0.0, 0.5, 1.0],
        tempo_events=[SourceTempoEvent(tick=0, time_seconds=0.0, bpm=120.0)],
        time_signatures=[
            SourceTimeSignatureEvent(
                tick=0,
                time_seconds=0.0,
                numerator=4,
                denominator=4,
            )
        ],
        arrangements=[
            PreviewArrangement(
                instrument="lead",
                part_index=0,
                part_id="P1",
                part_name="Lead Guitar",
                tuning_midi=[40, 45, 50, 55, 59, 64],
                output_json="sources/imported/lead.json",
                note_count=len(notes),
                notes=notes,
            )
        ],
    )


def test_builds_one_synchronized_gui_workspace_state() -> None:
    state = build_preview_workspace_state(
        _snapshot(),
        viewport_start_seconds=0.4,
        viewport_end_seconds=0.9,
        playhead_seconds=0.5,
    )

    assert state.viewport.beat_times_seconds == [0.5]
    assert [note.event_index for note in state.viewport.lanes[0].notes] == [0, 1]
    assert [note.event_index for note in state.playhead.lanes[0].active_notes] == [0]
    assert state.playhead.lanes[0].next_note is not None
    assert state.playhead.lanes[0].next_note.event_index == 1
    assert state.musical_context.previous_beat_index == 1
    assert state.musical_context.next_beat_index == 2
    assert state.musical_context.local_bpm == pytest.approx(120.0)
    assert state.fretboard.lanes[0].active_markers[0].event_index == 0
    assert state.fretboard.lanes[0].upcoming_marker is not None
    assert state.fretboard.lanes[0].upcoming_marker.event_index == 1
    assert state.review_required_total == 1
    assert state.review_navigation is not None
    assert state.review_navigation.current.review_id == "lead:1"


def test_empty_review_queue_has_no_navigation_state() -> None:
    state = build_preview_workspace_state(
        _snapshot(include_review=False),
        viewport_start_seconds=0.0,
        viewport_end_seconds=1.0,
        playhead_seconds=0.5,
    )

    assert state.review_required_total == 0
    assert state.review_navigation is None


def test_workspace_outputs_do_not_mutate_trusted_snapshot() -> None:
    snapshot = _snapshot()
    state = build_preview_workspace_state(
        snapshot,
        viewport_start_seconds=0.4,
        viewport_end_seconds=0.9,
        playhead_seconds=0.5,
    )

    state.viewport.lanes[0].notes[0].techniques.append("preview-only")
    state.playhead.lanes[0].active_notes[0].techniques.append("playhead-only")
    assert snapshot.arrangements[0].notes[0].techniques == ["accent"]


def test_workspace_preserves_consumer_validation_boundaries() -> None:
    with pytest.raises(ValueError, match="greater than or equal"):
        build_preview_workspace_state(
            _snapshot(),
            viewport_start_seconds=1.0,
            viewport_end_seconds=0.5,
            playhead_seconds=0.5,
        )

    snapshot = _snapshot()
    snapshot.beat_times_seconds = [0.0, 0.5, 0.5]
    with pytest.raises(ValueError, match="strictly increasing"):
        build_preview_workspace_state(
            snapshot,
            viewport_start_seconds=0.0,
            viewport_end_seconds=1.0,
            playhead_seconds=0.25,
        )
