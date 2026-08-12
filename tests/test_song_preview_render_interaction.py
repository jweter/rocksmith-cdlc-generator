from __future__ import annotations

import math

import pytest

from rocksmith_cdlc_generator.song_preview import (
    PreviewArrangement,
    PreviewNoteEvent,
    SongPreviewSnapshot,
)
from rocksmith_cdlc_generator.song_preview_render import (
    build_preview_timeline_render_geometry,
)
from rocksmith_cdlc_generator.song_preview_render_interaction import (
    build_preview_timeline_interaction,
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
        techniques=[],
        import_confidence=0.9,
        trust_class=SourceTrustClass.symbolic_unverified,
        review_required=False,
    )


def _snapshot() -> SongPreviewSnapshot:
    notes = [
        _note(0, 0.75, 0.25),
        _note(1, 1.20, 0.20),
        _note(2, 1.80, 0.20),
    ]
    return SongPreviewSnapshot(
        source_filename="song.musicxml",
        source_sha256="a" * 64,
        beat_times_seconds=[0.0, 0.5, 1.0, 1.5, 2.0],
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


def test_maps_normalized_render_position_to_song_time_and_locator() -> None:
    snapshot = _snapshot()
    geometry = build_preview_timeline_render_geometry(snapshot, 0.5, 2.0)

    interaction = build_preview_timeline_interaction(
        snapshot,
        geometry,
        "lead",
        0.5,
        tolerance_seconds=0.10,
    )

    assert interaction.source_filename == "song.musicxml"
    assert interaction.source_sha256 == "a" * 64
    assert interaction.position_seconds == pytest.approx(1.25)
    assert interaction.locator.position_seconds == pytest.approx(1.25)
    assert interaction.locator.match_kind == "overlap"
    assert [candidate.selection_id for candidate in interaction.locator.candidates] == [
        "lead:1"
    ]


def test_maps_viewport_endpoints_without_clamping_or_hidden_policy() -> None:
    snapshot = _snapshot()
    geometry = build_preview_timeline_render_geometry(snapshot, 0.5, 2.0)

    left = build_preview_timeline_interaction(
        snapshot, geometry, "lead", 0.0, tolerance_seconds=0.0
    )
    right = build_preview_timeline_interaction(
        snapshot, geometry, "lead", 1.0, tolerance_seconds=0.0
    )

    assert left.position_seconds == 0.5
    assert right.position_seconds == 2.0
    assert left.locator.match_kind == "none"
    assert right.locator.match_kind == "nearby"
    assert [candidate.selection_id for candidate in right.locator.candidates] == ["lead:2"]
    assert right.locator.candidates[0].distance_seconds == 0.0


def test_explicit_tolerance_controls_nearby_selection() -> None:
    snapshot = _snapshot()
    geometry = build_preview_timeline_render_geometry(snapshot, 0.5, 2.0)
    x_fraction = (1.15 - 0.5) / 1.5

    strict = build_preview_timeline_interaction(
        snapshot, geometry, "lead", x_fraction, tolerance_seconds=0.04
    )
    nearby = build_preview_timeline_interaction(
        snapshot, geometry, "lead", x_fraction, tolerance_seconds=0.05
    )

    assert strict.locator.match_kind == "none"
    assert nearby.locator.match_kind == "nearby"
    assert nearby.locator.candidates[0].selection_id == "lead:1"
    assert nearby.locator.candidates[0].distance_seconds == pytest.approx(0.05)


def test_rejects_stale_render_geometry_provenance() -> None:
    snapshot = _snapshot()
    geometry = build_preview_timeline_render_geometry(snapshot, 0.5, 2.0)

    different = _snapshot()
    different.source_sha256 = "b" * 64
    with pytest.raises(ValueError, match="provenance"):
        build_preview_timeline_interaction(
            different, geometry, "lead", 0.5, tolerance_seconds=0.05
        )


def test_rejects_non_finite_or_out_of_range_interaction_inputs() -> None:
    snapshot = _snapshot()
    geometry = build_preview_timeline_render_geometry(snapshot, 0.5, 2.0)

    for value in [math.nan, math.inf, -math.inf]:
        with pytest.raises(ValueError, match="x fraction must be finite"):
            build_preview_timeline_interaction(
                snapshot, geometry, "lead", value, tolerance_seconds=0.05
            )
    for value in [-0.01, 1.01]:
        with pytest.raises(ValueError, match="between 0 and 1"):
            build_preview_timeline_interaction(
                snapshot, geometry, "lead", value, tolerance_seconds=0.05
            )
    for value in [math.nan, math.inf, -math.inf]:
        with pytest.raises(ValueError, match="tolerance must be finite"):
            build_preview_timeline_interaction(
                snapshot, geometry, "lead", 0.5, tolerance_seconds=value
            )
    with pytest.raises(ValueError, match="non-negative"):
        build_preview_timeline_interaction(
            snapshot, geometry, "lead", 0.5, tolerance_seconds=-0.01
        )


def test_rejects_mutated_inconsistent_render_duration() -> None:
    snapshot = _snapshot()
    geometry = build_preview_timeline_render_geometry(snapshot, 0.5, 2.0)
    geometry.duration_seconds = 99.0

    with pytest.raises(ValueError, match="inconsistent"):
        build_preview_timeline_interaction(
            snapshot, geometry, "lead", 0.5, tolerance_seconds=0.05
        )
