from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.song_preview import SongPreviewSnapshot
from rocksmith_cdlc_generator.song_preview_context import build_preview_musical_context
from rocksmith_cdlc_generator.source_import import SourceTempoEvent, SourceTimeSignatureEvent


def _snapshot() -> SongPreviewSnapshot:
    return SongPreviewSnapshot(
        source_filename="song.musicxml",
        source_sha256="a" * 64,
        beat_times_seconds=[0.0, 0.5, 1.1, 1.6],
        tempo_events=[
            SourceTempoEvent(tick=0, time_seconds=0.0, bpm=120.0),
            SourceTempoEvent(tick=960, time_seconds=1.1, bpm=100.0),
        ],
        time_signatures=[
            SourceTimeSignatureEvent(tick=0, time_seconds=0.0, numerator=4, denominator=4),
            SourceTimeSignatureEvent(tick=1440, time_seconds=1.6, numerator=3, denominator=4),
        ],
        arrangements=[],
    )


def test_builds_bracketing_beat_and_local_bpm_context() -> None:
    context = build_preview_musical_context(_snapshot(), 0.75)

    assert context.previous_beat_index == 1
    assert context.previous_beat_seconds == 0.5
    assert context.next_beat_index == 2
    assert context.next_beat_seconds == 1.1
    assert context.beat_phase == pytest.approx(5 / 12)
    assert context.local_bpm == pytest.approx(100.0)
    assert context.tempo_event is not None
    assert context.tempo_event.bpm == 120.0
    assert context.time_signature is not None
    assert context.time_signature.numerator == 4


def test_uses_latest_source_metadata_at_playhead() -> None:
    context = build_preview_musical_context(_snapshot(), 1.7)

    assert context.previous_beat_index == 3
    assert context.next_beat_index is None
    assert context.local_bpm is None
    assert context.beat_phase is None
    assert context.tempo_event is not None
    assert context.tempo_event.bpm == 100.0
    assert context.time_signature is not None
    assert context.time_signature.numerator == 3


def test_before_first_beat_has_only_next_beat() -> None:
    snapshot = _snapshot()
    snapshot.beat_times_seconds = [0.5, 1.0]

    context = build_preview_musical_context(snapshot, 0.25)

    assert context.previous_beat_index is None
    assert context.next_beat_index == 0
    assert context.next_beat_seconds == 0.5
    assert context.local_bpm is None


def test_rejects_non_monotonic_timing_contracts() -> None:
    snapshot = _snapshot()
    snapshot.beat_times_seconds = [0.0, 0.5, 0.5]
    with pytest.raises(ValueError, match="beat grid"):
        build_preview_musical_context(snapshot, 0.25)

    snapshot = _snapshot()
    snapshot.tempo_events = [
        SourceTempoEvent(tick=0, time_seconds=1.0, bpm=120.0),
        SourceTempoEvent(tick=480, time_seconds=0.5, bpm=110.0),
    ]
    with pytest.raises(ValueError, match="tempo events"):
        build_preview_musical_context(snapshot, 0.25)


def test_rejects_negative_position() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        build_preview_musical_context(_snapshot(), -0.01)
