"""Shared physical open-string tuning contract for preview and source evidence.

A declared tuning is a symbolic source fact, not independent proof of a
recorded instrument's tuning or a playable Rocksmith export.
"""
from __future__ import annotations


def explicit_tuning_is_valid(
    instrument: str, tuning_midi: list[int] | tuple[int, ...] | None,
) -> bool:
    """Fail closed on absent/malformed role-specific physical-string pitches."""
    if tuning_midi is None or instrument not in {"bass", "lead", "rhythm"}:
        return False
    if not isinstance(tuning_midi, (list, tuple)):
        return False
    expected_lengths = range(4, 7) if instrument == "bass" else range(6, 9)
    return (
        len(tuning_midi) in expected_lengths
        and all(type(pitch) is int and 0 <= pitch <= 127 for pitch in tuning_midi)
    )
