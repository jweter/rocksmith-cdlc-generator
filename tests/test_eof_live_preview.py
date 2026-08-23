from __future__ import annotations

from rocksmith_cdlc_generator.eof_live_preview import (
    highway_notes,
    live_window,
    notes_in_window,
    string_count,
    time_fraction,
)
from rocksmith_cdlc_generator.song_preview import PreviewArrangement, PreviewNoteEvent
from rocksmith_cdlc_generator.source_import import SourceTrustClass


def _note(index: int, start: float, duration: float, string: int, fret: int) -> PreviewNoteEvent:
    return PreviewNoteEvent(
        event_index=index,
        start_seconds=start,
        duration_seconds=duration,
        midi=40 + fret,
        string_index=string,
        fret=fret,
        import_confidence=1.0,
        trust_class=SourceTrustClass.symbolic_verified,
        review_required=False,
    )


def _arrangement() -> PreviewArrangement:
    return PreviewArrangement(
        instrument="lead",
        part_index=0,
        part_id="P1",
        part_name="Lead",
        tuning_midi=[40, 45, 50, 55, 59, 64],
        output_json="sources/imported/lead.json",
        note_count=4,
        notes=[
            _note(0, 9.0, 0.5, 0, 3),
            _note(1, 10.0, 1.0, 1, 5),
            _note(2, 12.0, 0.25, 2, 7),
            _note(3, 18.0, 0.25, 3, 9),
        ],
    )


def test_live_window_keeps_playhead_visible_and_bounded() -> None:
    window = live_window(playhead_seconds=10.0, duration_seconds=20.0)
    assert window.start_seconds == 8.5
    assert window.end_seconds == 16.0
    assert window.playhead_seconds == 10.0
    assert 0.0 < time_fraction(window.playhead_seconds, window) < 1.0

    end = live_window(playhead_seconds=19.5, duration_seconds=20.0)
    assert end.end_seconds == 20.0
    assert end.start_seconds == 18.0


def test_live_preview_uses_physical_string_count_and_clips_visible_notes() -> None:
    arrangement = _arrangement()
    window = live_window(playhead_seconds=10.0, duration_seconds=20.0)
    assert string_count(arrangement) == 6
    assert [note.event_index for note in notes_in_window(arrangement, window)] == [0, 1, 2]


def test_highway_projection_contains_only_current_and_upcoming_notes() -> None:
    arrangement = _arrangement()
    window = live_window(playhead_seconds=10.0, duration_seconds=20.0)
    projected = highway_notes(arrangement, window)

    assert [item.note.event_index for item in projected] == [1, 2]
    assert projected[0].progress == 0.0
    assert 0.0 < projected[1].progress < 1.0
    assert projected[0].x_fraction == (1.5 / 6.0)
    assert all(item.width_fraction > 0 for item in projected)


def test_string_count_falls_back_to_observed_positions_then_instrument_default() -> None:
    arrangement = _arrangement().model_copy(update={"tuning_midi": None})
    assert string_count(arrangement) == 4

    empty_bass = PreviewArrangement(
        instrument="bass",
        part_index=2,
        part_id="P3",
        part_name="Bass",
        output_json="sources/imported/bass.json",
        note_count=0,
        notes=[],
    )
    assert string_count(empty_bass) == 4
