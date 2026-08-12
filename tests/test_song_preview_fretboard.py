from __future__ import annotations

from rocksmith_cdlc_generator.song_preview import PreviewNoteEvent
from rocksmith_cdlc_generator.song_preview_fretboard import build_preview_fretboard_state
from rocksmith_cdlc_generator.song_preview_playhead import (
    PreviewPlayheadLane,
    PreviewPlayheadState,
)
from rocksmith_cdlc_generator.source_import import SourceTrustClass


def _note(*, event_index: int, string_index: int | None, fret: int | None) -> PreviewNoteEvent:
    return PreviewNoteEvent(
        event_index=event_index,
        start_seconds=1.0,
        duration_seconds=0.25,
        midi=64,
        note_name="E4",
        string_index=string_index,
        fret=fret,
        techniques=["accent"],
        import_confidence=0.8,
        trust_class=SourceTrustClass.symbolic_unverified,
        review_required=True,
    )


def test_projects_active_and_upcoming_physical_positions() -> None:
    playhead = PreviewPlayheadState(
        position_seconds=1.1,
        lanes=[
            PreviewPlayheadLane(
                instrument="lead",
                part_name="Lead Guitar",
                tuning_midi=[40, 45, 50, 55, 59, 64],
                active_notes=[_note(event_index=3, string_index=5, fret=0)],
                next_note=_note(event_index=4, string_index=4, fret=5),
            )
        ],
    )

    state = build_preview_fretboard_state(playhead)

    lane = state.lanes[0]
    assert lane.instrument == "lead"
    assert lane.tuning_midi == [40, 45, 50, 55, 59, 64]
    assert lane.active_markers[0].event_index == 3
    assert lane.active_markers[0].string_index == 5
    assert lane.active_markers[0].fret == 0
    assert lane.active_markers[0].is_active is True
    assert lane.upcoming_marker is not None
    assert lane.upcoming_marker.event_index == 4
    assert lane.upcoming_marker.is_active is False


def test_preserves_unmapped_events_instead_of_inventing_positions() -> None:
    playhead = PreviewPlayheadState(
        position_seconds=2.0,
        lanes=[
            PreviewPlayheadLane(
                instrument="bass",
                part_name="Bass",
                tuning_midi=[28, 33, 38, 43],
                active_notes=[_note(event_index=7, string_index=None, fret=None)],
                next_note=_note(event_index=8, string_index=None, fret=None),
            )
        ],
    )

    lane = build_preview_fretboard_state(playhead).lanes[0]

    assert lane.active_markers == []
    assert lane.unmapped_active_event_indices == [7]
    assert lane.upcoming_marker is None
    assert lane.unmapped_upcoming_event_index == 8


def test_omits_lane_without_explicit_tuning() -> None:
    playhead = PreviewPlayheadState(
        position_seconds=0.0,
        lanes=[
            PreviewPlayheadLane(
                instrument="rhythm",
                part_name="Rhythm Guitar",
                tuning_midi=None,
                active_notes=[],
                next_note=None,
            )
        ],
    )

    assert build_preview_fretboard_state(playhead).lanes == []


def test_returned_state_does_not_mutate_playhead() -> None:
    playhead = PreviewPlayheadState(
        position_seconds=1.1,
        lanes=[
            PreviewPlayheadLane(
                instrument="lead",
                part_name="Lead Guitar",
                tuning_midi=[40, 45, 50, 55, 59, 64],
                active_notes=[_note(event_index=1, string_index=5, fret=0)],
            )
        ],
    )

    state = build_preview_fretboard_state(playhead)
    state.lanes[0].tuning_midi[0] = 0

    assert playhead.lanes[0].tuning_midi == [40, 45, 50, 55, 59, 64]
