"""Keep overlapping (polyphonic) notes uncertain until independently isolated (#796 slice 38).

When two or more chart notes sound at the same time, a single-pitch detector cannot say
which one it heard, so a "match" on such a note proves nothing. This pure check finds the
notes that overlap another note and reports them as ``UNCERTAIN`` unless the caller names
them in ``isolated_note_ids`` (evidence from an independent source, for example a per-string
recording). It never promotes an overlapping note by itself, and it never changes a chart.

A note is ``(note_id, start_s, end_s)``. Two notes overlap when the shared time exceeds
``min_overlap_s`` (default 0.03 s; exactly equal does not overlap). Invalid input returns
``INVALID_INPUT`` with a named reason; it never raises and never reports ``CLEAR`` or
``ISOLATED`` for input it could not validate.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict

DEFAULT_MIN_OVERLAP_S = 0.03

ChordStatus = Literal["CLEAR", "UNCERTAIN", "ISOLATED", "INVALID_INPUT"]
NoteStatus = Literal["MONOPHONIC", "UNCERTAIN", "ISOLATED"]


class NoteVerdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    note_id: str
    status: NoteStatus


class ChordAmbiguityResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: ChordStatus
    reason: str = ""
    verdicts: tuple[NoteVerdict, ...] = ()
    overlapping_count: int = 0
    uncertain_count: int = 0


def _is_number(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
    )


def _invalid(reason: str) -> ChordAmbiguityResult:
    return ChordAmbiguityResult(status="INVALID_INPUT", reason=reason)


def assess_chord_ambiguity(
    notes: object,
    isolated_note_ids: object = (),
    min_overlap_s: object = DEFAULT_MIN_OVERLAP_S,
) -> ChordAmbiguityResult:
    """Classify each note as monophonic, uncertain (overlapping) or isolated (overlapping but proven)."""
    if isinstance(notes, (str, bytes)) or not isinstance(notes, Sequence):
        return _invalid("NOTES_NOT_A_SEQUENCE")
    if isinstance(isolated_note_ids, (str, bytes)) or not isinstance(
        isolated_note_ids, (Sequence, set, frozenset)
    ):
        return _invalid("ISOLATED_IDS_NOT_A_COLLECTION")
    if not _is_number(min_overlap_s) or float(min_overlap_s) < 0:  # type: ignore[arg-type]
        return _invalid("MIN_OVERLAP_INVALID")
    min_overlap = float(min_overlap_s)  # type: ignore[arg-type]

    parsed: list[tuple[str, float, float]] = []
    seen: set[str] = set()
    for item in notes:
        if isinstance(item, (str, bytes)) or not isinstance(item, Sequence) or len(item) != 3:
            return _invalid("NOTE_NOT_A_TRIPLE")
        note_id, start, end = item
        if not isinstance(note_id, str) or not note_id:
            return _invalid("NOTE_ID_INVALID")
        if note_id in seen:
            return _invalid("DUPLICATE_NOTE_ID")
        if not _is_number(start) or not _is_number(end) or float(start) < 0 or float(end) <= float(start):
            return _invalid("NOTE_TIMES_INVALID")
        seen.add(note_id)
        parsed.append((note_id, float(start), float(end)))

    isolated: set[str] = set()
    for value in isolated_note_ids:
        if not isinstance(value, str):
            return _invalid("ISOLATED_ID_INVALID")
        if value not in seen:
            return _invalid("ISOLATED_ID_UNKNOWN_NOTE")
        isolated.add(value)

    if not parsed:
        return _invalid("NO_NOTES")

    ordered = sorted(range(len(parsed)), key=lambda i: (parsed[i][1], parsed[i][2]))
    overlapping: set[int] = set()
    active: list[int] = []
    for index in ordered:
        start = parsed[index][1]
        active = [a for a in active if parsed[a][2] - start > min_overlap]
        for other in active:
            shared = min(parsed[other][2], parsed[index][2]) - start
            if shared > min_overlap:
                overlapping.add(other)
                overlapping.add(index)
        active.append(index)

    verdicts: list[NoteVerdict] = []
    uncertain = 0
    for i, (note_id, _start, _end) in enumerate(parsed):
        if i not in overlapping:
            verdicts.append(NoteVerdict(note_id=note_id, status="MONOPHONIC"))
        elif note_id in isolated:
            verdicts.append(NoteVerdict(note_id=note_id, status="ISOLATED"))
        else:
            verdicts.append(NoteVerdict(note_id=note_id, status="UNCERTAIN"))
            uncertain += 1

    if not overlapping:
        status: ChordStatus = "CLEAR"
    elif uncertain:
        status = "UNCERTAIN"
    else:
        status = "ISOLATED"
    return ChordAmbiguityResult(
        status=status,
        verdicts=tuple(verdicts),
        overlapping_count=len(overlapping),
        uncertain_count=uncertain,
    )
