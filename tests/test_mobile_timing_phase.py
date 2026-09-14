from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.beats import BeatEvent, TempoMap
from rocksmith_cdlc_generator.mobile_timing_phase import beat_phase_delta, continuous_beat_position


def _tempo_map() -> TempoMap:
    return TempoMap(
        engine="fixture",
        beats=[
            BeatEvent(time=1.0, beat=1, measure=1, bpm=120.0, confidence=1.0, is_downbeat=True),
            BeatEvent(time=1.5, beat=2, measure=1, bpm=120.0, confidence=1.0),
            BeatEvent(time=2.0, beat=3, measure=1, bpm=120.0, confidence=1.0),
            BeatEvent(time=2.75, beat=4, measure=1, bpm=80.0, confidence=1.0),
        ],
    )


def test_continuous_beat_position_uses_authoritative_intervals() -> None:
    tempo_map = _tempo_map()

    assert continuous_beat_position(tempo_map, 1.0) == pytest.approx(1.0)
    assert continuous_beat_position(tempo_map, 1.25) == pytest.approx(1.5)
    assert continuous_beat_position(tempo_map, 2.375) == pytest.approx(3.5)


def test_beat_phase_delta_handles_variable_tempo_without_seconds_as_beats() -> None:
    tempo_map = _tempo_map()

    assert beat_phase_delta(
        tempo_map,
        observed_seconds=2.375,
        expected_seconds=1.75,
    ) == pytest.approx(1.0)


def test_projection_fails_closed_outside_authoritative_beat_lattice() -> None:
    tempo_map = _tempo_map()

    with pytest.raises(ValueError, match="outside the authoritative beat lattice"):
        continuous_beat_position(tempo_map, 0.5)
    with pytest.raises(ValueError, match="outside the authoritative beat lattice"):
        continuous_beat_position(tempo_map, 3.0)


def test_projection_requires_two_authoritative_beats() -> None:
    tempo_map = TempoMap(
        engine="fixture",
        beats=[BeatEvent(time=1.0, beat=1, measure=1, bpm=120.0, confidence=1.0)],
    )

    with pytest.raises(ValueError, match="at least two authoritative beats"):
        continuous_beat_position(tempo_map, 1.0)
