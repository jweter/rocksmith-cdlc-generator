from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.song_preview import (
    PreviewArrangement,
    PreviewNoteEvent,
    SongPreviewSnapshot,
)
from rocksmith_cdlc_generator.song_preview_render import (
    build_preview_timeline_render_geometry,
)
from rocksmith_cdlc_generator.source_import import SourceTrustClass


def _note(event_index: int, start: float, duration: float) -> PreviewNoteEvent:
    return PreviewNoteEvent(
        event_index=event_index,
        start_seconds=start,
        duration_seconds=duration,
        midi=60 + event_index,
        note_name="C4",
        string_index=event_index % 6,
        fret=event_index,
        techniques=["accent"],
        import_confidence=0.9,
        trust_class=SourceTrustClass.symbolic_unverified,
        review_required=event_index == 1,
    )


def _snapshot() -> SongPreviewSnapshot:
    notes = [
        _note(0, 0.25, 0.5),
        _note(1, 1.0, 1.0),
        _note(2, 2.0, 0.5),
    ]
    return SongPreviewSnapshot(
        source_filename="song.musicxml",
        source_sha256="a" * 64,
        beat_times_seconds=[0.0, 0.5, 1.0, 1.5, 2.0, 2.5],
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


def test_builds_normalized_geometry_with_stable_beat_and_event_ids() -> None:
    geometry = build_preview_timeline_render_geometry(_snapshot(), 0.5, 2.0)

    assert geometry.source_filename == "song.musicxml"
    assert geometry.source_sha256 == "a" * 64
    assert geometry.duration_seconds == 1.5
    assert [(beat.beat_index, beat.x_fraction) for beat in geometry.beats] == [
        (1, 0.0),
        (2, pytest.approx(1 / 3)),
        (3, pytest.approx(2 / 3)),
        (4, 1.0),
    ]

    events = geometry.lanes[0].events
    assert [event.selection_id for event in events] == ["lead:0", "lead:1"]
    assert events[0].clipped_start_seconds == 0.5
    assert events[0].clipped_end_seconds == 0.75
    assert events[0].x_start_fraction == 0.0
    assert events[0].x_end_fraction == pytest.approx(1 / 6)
    assert events[1].x_start_fraction == pytest.approx(1 / 3)
    assert events[1].x_end_fraction == 1.0


def test_render_projection_preserves_original_event_timing_and_is_a_deep_copy() -> None:
    snapshot = _snapshot()
    geometry = build_preview_timeline_render_geometry(snapshot, 0.5, 1.5)

    rendered = geometry.lanes[0].events[0]
    assert rendered.clipped_start_seconds == 0.5
    assert rendered.event.start_seconds == 0.25
    assert rendered.event.end_seconds == 0.75

    rendered.event.techniques.append("preview-only")
    assert snapshot.arrangements[0].notes[0].techniques == ["accent"]


def test_event_starting_exactly_at_viewport_end_is_not_zero_width() -> None:
    geometry = build_preview_timeline_render_geometry(_snapshot(), 1.0, 2.0)

    assert [event.selection_id for event in geometry.lanes[0].events] == ["lead:1"]


def test_rejects_zero_width_or_invalid_viewport() -> None:
    snapshot = _snapshot()

    with pytest.raises(ValueError, match="non-negative"):
        build_preview_timeline_render_geometry(snapshot, -0.1, 1.0)
    with pytest.raises(ValueError, match="greater than start"):
        build_preview_timeline_render_geometry(snapshot, 1.0, 1.0)
    with pytest.raises(ValueError, match="greater than start"):
        build_preview_timeline_render_geometry(snapshot, 2.0, 1.0)


def test_rejects_ambiguous_or_non_monotonic_render_contracts() -> None:
    duplicate_role = _snapshot()
    duplicate_role.arrangements.append(duplicate_role.arrangements[0].model_copy(deep=True))
    with pytest.raises(ValueError, match="duplicate arrangement roles"):
        build_preview_timeline_render_geometry(duplicate_role, 0.0, 1.0)

    duplicate_event = _snapshot()
    duplicate_event.arrangements[0].notes.append(_note(1, 2.25, 0.25))
    with pytest.raises(ValueError, match="duplicate event indices"):
        build_preview_timeline_render_geometry(duplicate_event, 0.0, 1.0)

    bad_beats = _snapshot()
    bad_beats.beat_times_seconds = [0.0, 0.5, 0.5, 1.0]
    with pytest.raises(ValueError, match="strictly increasing"):
        build_preview_timeline_render_geometry(bad_beats, 0.0, 1.0)
