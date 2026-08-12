from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.song_preview import SongPreviewSnapshot
from rocksmith_cdlc_generator.song_preview_loop import (
    build_preview_loop_range,
    wrap_preview_playhead,
)


def _snapshot() -> SongPreviewSnapshot:
    return SongPreviewSnapshot(
        source_filename="song.musicxml",
        source_sha256="a" * 64,
        beat_times_seconds=[0.0, 0.5, 1.0, 1.5, 2.0],
        arrangements=[],
    )


def test_builds_loop_range_with_full_song_beat_indices() -> None:
    loop = build_preview_loop_range(_snapshot(), 0.5, 1.6)

    assert loop.start_seconds == 0.5
    assert loop.end_seconds == 1.6
    assert loop.duration_seconds == pytest.approx(1.1)
    assert loop.beat_indices == [1, 2, 3]
    assert loop.beat_times_seconds == [0.5, 1.0, 1.5]


def test_loop_end_is_exclusive_for_beat_membership() -> None:
    loop = build_preview_loop_range(_snapshot(), 0.5, 1.5)

    assert loop.beat_indices == [1, 2]
    assert loop.beat_times_seconds == [0.5, 1.0]


def test_loop_can_cover_region_without_canonical_beats() -> None:
    loop = build_preview_loop_range(_snapshot(), 2.1, 2.4)

    assert loop.beat_indices == []
    assert loop.beat_times_seconds == []


def test_wraps_at_end_and_after_multiple_loop_lengths() -> None:
    loop = build_preview_loop_range(_snapshot(), 0.5, 1.5)

    assert wrap_preview_playhead(loop, 1.49) == pytest.approx(1.49)
    assert wrap_preview_playhead(loop, 1.5) == pytest.approx(0.5)
    assert wrap_preview_playhead(loop, 2.75) == pytest.approx(0.75)


def test_pre_roll_position_before_loop_is_unchanged() -> None:
    loop = build_preview_loop_range(_snapshot(), 0.5, 1.5)

    assert wrap_preview_playhead(loop, 0.25) == pytest.approx(0.25)


def test_rejects_invalid_loop_bounds_and_negative_playhead() -> None:
    snapshot = _snapshot()

    with pytest.raises(ValueError, match="non-negative"):
        build_preview_loop_range(snapshot, -0.1, 1.0)
    with pytest.raises(ValueError, match="greater than loop start"):
        build_preview_loop_range(snapshot, 1.0, 1.0)
    with pytest.raises(ValueError, match="greater than loop start"):
        build_preview_loop_range(snapshot, 1.0, 0.5)

    loop = build_preview_loop_range(snapshot, 0.5, 1.5)
    with pytest.raises(ValueError, match="non-negative"):
        wrap_preview_playhead(loop, -0.01)
