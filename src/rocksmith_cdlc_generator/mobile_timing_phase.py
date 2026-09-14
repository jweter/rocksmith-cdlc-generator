"""Deterministic beat-space projection for privacy-safe mobile timing review.

This module consumes the authoritative project TempoMap. It does not infer tempo,
read private media, or create a second timing authority.
"""

from __future__ import annotations

from .beats import TempoMap


def continuous_beat_position(tempo_map: TempoMap, time_seconds: float) -> float:
    """Project an in-range recording timestamp onto the authoritative beat lattice.

    Positions are 1-based continuous beat ordinals in TempoMap order. Values outside
    the observed beat lattice fail closed rather than extrapolating unverified phase.
    """
    if time_seconds < 0.0:
        raise ValueError("time_seconds must be non-negative")
    beats = tempo_map.beats
    if len(beats) < 2:
        raise ValueError("beat-space projection requires at least two authoritative beats")
    if time_seconds < beats[0].time or time_seconds > beats[-1].time:
        raise ValueError("timestamp lies outside the authoritative beat lattice")

    for index, beat in enumerate(beats):
        if time_seconds == beat.time:
            return float(index + 1)
        if index + 1 >= len(beats):
            break
        following = beats[index + 1]
        if beat.time < time_seconds < following.time:
            fraction = (time_seconds - beat.time) / (following.time - beat.time)
            return float(index + 1) + fraction

    raise ValueError("timestamp could not be projected onto the authoritative beat lattice")


def beat_phase_delta(
    tempo_map: TempoMap, *, observed_seconds: float, expected_seconds: float
) -> float:
    """Return observed-minus-expected displacement in authoritative beat units."""
    observed = continuous_beat_position(tempo_map, observed_seconds)
    expected = continuous_beat_position(tempo_map, expected_seconds)
    return observed - expected
