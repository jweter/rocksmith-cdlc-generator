"""Flag notes that sustain through audio-silent gaps (#796 slice 49).

A chart note whose sustain runs on into a stretch of the original recording that is
silent is a *phantom sustain*: the player is told to hold a note the music does not play.
This is a pure check over note timings and independently measured silent gaps; it never
changes a chart. Invalid input returns ``INVALID_INPUT`` with a named reason (it never
raises and never reports ``CLEAR`` for input it could not validate).

A note ``(start_s, sustain_s)`` is flagged when it begins before a gap starts and its
sustain extends more than ``tolerance_s`` past the gap's start (the overlap is capped at
the gap's end). An overlap exactly equal to the tolerance is not flagged. A note that
starts inside a gap is a different defect (an onset in silence) and is not judged here.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict

DEFAULT_TOLERANCE_S = 0.05

PhantomSustainStatus = Literal["CLEAR", "PHANTOM_SUSTAIN", "INVALID_INPUT"]


class FlaggedNote(BaseModel):
    model_config = ConfigDict(frozen=True)

    note_index: int
    overlap_s: float


class PhantomSustainResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: PhantomSustainStatus
    reason: str = ""
    flagged: tuple[FlaggedNote, ...] = ()


def _is_number(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
    )


def _invalid(reason: str) -> PhantomSustainResult:
    return PhantomSustainResult(status="INVALID_INPUT", reason=reason)


def _pairs(raw: object) -> list[tuple[float, float]] | None:
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        return None
    pairs: list[tuple[float, float]] = []
    for item in raw:
        if isinstance(item, (str, bytes)) or not isinstance(item, Sequence) or len(item) != 2:
            return None
        first, second = item
        if not _is_number(first) or not _is_number(second):
            return None
        pairs.append((float(first), float(second)))
    return pairs


def check_phantom_sustain(
    notes: object,
    silent_gaps: object,
    tolerance_s: object = DEFAULT_TOLERANCE_S,
) -> PhantomSustainResult:
    """Return which notes (if any) sustain more than ``tolerance_s`` into a silent gap."""

    if not _is_number(tolerance_s) or float(tolerance_s) < 0:  # type: ignore[arg-type]
        return _invalid("INVALID_TOLERANCE")
    tolerance = float(tolerance_s)  # type: ignore[arg-type]

    note_pairs = _pairs(notes)
    if note_pairs is None or any(start < 0 or sustain < 0 for start, sustain in note_pairs):
        return _invalid("INVALID_NOTES")
    gap_pairs = _pairs(silent_gaps)
    if gap_pairs is None or any(start < 0 or end <= start for start, end in gap_pairs):
        return _invalid("INVALID_GAPS")

    flagged: list[FlaggedNote] = []
    for index, (start, sustain) in enumerate(note_pairs):
        note_end = start + sustain
        worst = 0.0
        for gap_start, gap_end in gap_pairs:
            if gap_start <= start:
                continue  # onset inside silence is a different defect
            overlap = min(note_end, gap_end) - gap_start
            worst = max(worst, overlap)
        if worst > tolerance:
            flagged.append(FlaggedNote(note_index=index, overlap_s=worst))

    if flagged:
        return PhantomSustainResult(
            status="PHANTOM_SUSTAIN", reason="SUSTAIN_THROUGH_SILENCE", flagged=tuple(flagged)
        )
    return PhantomSustainResult(status="CLEAR")
