from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.song_preview import SongPreviewSnapshot
from rocksmith_cdlc_generator.song_preview_click import build_preview_click_schedule


def _snapshot(beats: list[float]) -> SongPreviewSnapshot:
    return SongPreviewSnapshot(
        source_filename="song.musicxml",
        source_sha256="a" * 64,
        beat_times_seconds=beats,
        arrangements=[],
    )


def test_builds_variable_tempo_schedule_from_canonical_beats() -> None:
    schedule = build_preview_click_schedule(_snapshot([0.0, 0.5, 1.1, 1.6]))

    assert [event.beat_index for event in schedule.events] == [0, 1, 2, 3]
    assert [event.time_seconds for event in schedule.events] == [0.0, 0.5, 1.1, 1.6]
    assert schedule.events[0].interval_from_previous_seconds is None
    assert schedule.events[0].interval_to_next_seconds == pytest.approx(0.5)
    assert schedule.events[0].local_bpm == pytest.approx(120.0)
    assert schedule.events[1].local_bpm == pytest.approx(100.0)
    assert schedule.events[2].local_bpm == pytest.approx(120.0)
    assert schedule.events[3].local_bpm is None


def test_range_filter_preserves_full_song_beat_indices() -> None:
    schedule = build_preview_click_schedule(
        _snapshot([0.0, 0.5, 1.0, 1.5]),
        start_seconds=0.4,
        end_seconds=1.1,
    )

    assert [event.beat_index for event in schedule.events] == [1, 2]
    assert [event.time_seconds for event in schedule.events] == [0.5, 1.0]
    assert schedule.events[0].interval_from_previous_seconds == pytest.approx(0.5)
    assert schedule.events[1].interval_to_next_seconds == pytest.approx(0.5)


def test_empty_grid_produces_empty_zero_length_schedule() -> None:
    schedule = build_preview_click_schedule(_snapshot([]))

    assert schedule.start_seconds == 0.0
    assert schedule.end_seconds == 0.0
    assert schedule.events == []


def test_rejects_invalid_ranges_and_non_monotonic_grid() -> None:
    snapshot = _snapshot([0.0, 0.5, 1.0])

    with pytest.raises(ValueError, match="non-negative"):
        build_preview_click_schedule(snapshot, start_seconds=-0.1)
    with pytest.raises(ValueError, match="greater than or equal"):
        build_preview_click_schedule(snapshot, start_seconds=1.0, end_seconds=0.5)
    with pytest.raises(ValueError, match="strictly increasing"):
        build_preview_click_schedule(_snapshot([0.0, 0.5, 0.5]))
