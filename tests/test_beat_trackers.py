from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.beat_quality import review_tempo_map
from rocksmith_cdlc_generator.beat_trackers import LibrosaBeatTracker, LibrosaPLPTracker
from tests.audio_factory import write_click_track


def _median_absolute_error_ms(detected: list[float], expected: list[float]) -> float:
    pairs = zip(detected[: len(expected)], expected[: len(detected)])
    errors = sorted(abs(a - b) * 1000.0 for a, b in pairs)
    if not errors:
        return float("inf")
    middle = len(errors) // 2
    if len(errors) % 2:
        return errors[middle]
    return (errors[middle - 1] + errors[middle]) / 2.0


@pytest.mark.parametrize("tracker", [LibrosaBeatTracker(), LibrosaPLPTracker()])
def test_tracker_detects_synthetic_120_bpm(tmp_path: Path, tracker) -> None:
    audio = tmp_path / "clicks.wav"
    expected = write_click_track(audio, bpm=120.0, beats=24)
    tempo_map = tracker.analyze(audio)

    assert len(tempo_map.beats) >= 18
    assert tempo_map.median_bpm is not None
    assert abs(tempo_map.median_bpm - 120.0) < 4.0

    detected = [event.time for event in tempo_map.beats]
    # A constant phase offset is acceptable for this first engine benchmark; gross drift is not.
    if detected and expected:
        offset = detected[0] - expected[0]
        aligned = [value - offset for value in detected]
        assert _median_absolute_error_ms(aligned, expected) < 45.0

    review = review_tempo_map(tempo_map)
    assert review.status in {"PASS", "WARNING"}
