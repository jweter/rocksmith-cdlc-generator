from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class PlayabilityFinding:
    code: str
    severity: str
    message: str
    fret_span: int


def fretted_span(frets: Iterable[int]) -> int:
    """Return physical fretted span, excluding open/muted strings.

    Open strings do not consume left-hand span. Negative values are treated as muted or
    absent and are ignored. A single fretted note has zero span.
    """
    used = sorted(int(fret) for fret in frets if int(fret) > 0)
    if len(used) < 2:
        return 0
    return used[-1] - used[0]


def chord_playability_finding(frets: Iterable[int]) -> PlayabilityFinding | None:
    """Conservatively classify simultaneous fretted spans.

    Seven or more frets is treated as physically implausible for a normal simultaneous
    one-hand chord and blocks export pending review. Five or six frets is unusual enough
    to require explicit review, but is not automatically rejected because advanced
    voicings and unusual hand sizes exist. Smaller spans are left alone.
    """
    values = [int(fret) for fret in frets]
    span = fretted_span(values)
    used = sorted(fret for fret in values if fret > 0)
    if span >= 7:
        return PlayabilityFinding(
            code="implausible_chord_fret_span",
            severity="FAIL",
            message=f"Chord spans frets {used[0]}-{used[-1]} ({span}-fret span) and is physically implausible for one normal fretting hand.",
            fret_span=span,
        )
    if span >= 5:
        return PlayabilityFinding(
            code="wide_chord_fret_span",
            severity="WARNING",
            message=f"Chord spans frets {used[0]}-{used[-1]} ({span}-fret span); confirm that this fingering is intentional and playable.",
            fret_span=span,
        )
    return None
