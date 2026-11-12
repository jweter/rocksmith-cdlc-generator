"""Arrangement-presence and Bass/Lead/Rhythm symmetry metric for the corpus differential comparator (issue #693, slice 5).

Pure and file-free: it only inspects the arrangement names already found in a package.
"""

from __future__ import annotations

from typing import Sequence, TypedDict


class ArrangementPresence(TypedDict):
    bass: bool
    lead: bool
    rhythm: bool
    symmetric: bool


def arrangement_presence(arrangement_names: Sequence[str]) -> ArrangementPresence:
    """Classify which of Bass, Lead and Rhythm are present among ``arrangement_names`` (case-insensitive exact match)."""
    lowered = {name.lower() for name in arrangement_names}
    bass = "bass" in lowered
    lead = "lead" in lowered
    rhythm = "rhythm" in lowered
    return {
        "bass": bass,
        "lead": lead,
        "rhythm": rhythm,
        "symmetric": bass and lead and rhythm,
    }
