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



def test_guitar_tuning_proof_prevents_phantom_positions_and_keeps_review_indices() -> None:
    """Neither note role nor a stored fret independently establishes its pitch."""
    down_tuned = [38, 43, 48, 53, 57, 62]
    # The sixth open string is D4 (62), not E4 (64) in this guitar tuning.
    good = _note(event_index=10, string_index=5, fret=0).model_copy(update={"midi": 62})
    wrong_pitch = _note(event_index=11, string_index=5, fret=0)
    wrong_string = _note(event_index=12, string_index=6, fret=0)
    late = _note(event_index=13, string_index=5, fret=1).model_copy(update={"midi": 64})
    playhead = PreviewPlayheadState(
        position_seconds=1.1,
        lanes=[PreviewPlayheadLane(
            instrument="rhythm", part_name="Rhythm", tuning_midi=down_tuned,
            active_notes=[good, wrong_pitch, wrong_string],
            next_note=late,
        )],
    )
    lane = build_preview_fretboard_state(playhead).lanes[0]
    assert [marker.event_index for marker in lane.active_markers] == [10]
    assert lane.unmapped_active_event_indices == [11, 12]
    assert lane.upcoming_marker is None
    assert lane.unmapped_upcoming_event_index == 13
    # Source/view-model remains untouched, and no standard tuning is injected.
    assert playhead.lanes[0].tuning_midi == down_tuned


def test_guitar_tuning_proof_rejects_wrong_shape_and_non_pitch_data() -> None:
    from types import SimpleNamespace
    from rocksmith_cdlc_generator.song_preview_fretboard import (
        explicit_tuning_is_valid, note_matches_explicit_tuning,
    )

    assert not explicit_tuning_is_valid("lead", None)
    assert not explicit_tuning_is_valid("lead", [40, 45, 50, 55, 59])
    assert not explicit_tuning_is_valid("rhythm", [40, 45, 50, 55, True, 64])
    assert not explicit_tuning_is_valid("guitar", [40, 45, 50, 55, 59, 64])
    assert explicit_tuning_is_valid("bass", [28, 33, 38, 43])
    assert explicit_tuning_is_valid("lead", [38, 43, 48, 53, 57, 62])

    note = SimpleNamespace(midi=64, string_index=5, fret=0)
    standard = [40, 45, 50, 55, 59, 64]
    dropped = [38, 43, 48, 53, 57, 62]
    assert note_matches_explicit_tuning(note, instrument="lead", tuning_midi=standard)
    assert not note_matches_explicit_tuning(note, instrument="lead", tuning_midi=dropped)
    assert not note_matches_explicit_tuning(note, instrument="lead", tuning_midi=None)
    assert not note_matches_explicit_tuning(note, instrument="lead", tuning_midi=standard[:5])
    assert not note_matches_explicit_tuning(
        SimpleNamespace(midi=64, string_index=5, fret=25),
        instrument="lead", tuning_midi=standard,
    )
    assert not note_matches_explicit_tuning(
        SimpleNamespace(midi=64, string_index=-1, fret=0),
        instrument="lead", tuning_midi=standard,
    )
