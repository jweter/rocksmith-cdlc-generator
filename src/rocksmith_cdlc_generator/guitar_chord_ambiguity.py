"""Polyphonic chord ambiguity negative-control for Lead/Rhythm guitar (#796 slice 38).

``guitar_onset_oracle.inspect_guitar_attack_onset`` corroborates a claimed note
onset with one measured local PCM energy transition. That measurement proves
only that *something* attacked near the claimed instant; it carries no
information attributing the shared energy to a single pitch. When a chart
claims two or more notes beginning at, or within the same bounded onset
tolerance as, one another -- a chord, exactly as Lead and Rhythm guitar
legitimately play -- the oracle's one shared attack measurement cannot be
independent confirmation of any one member note, no matter how strongly the
shared attack measures.

This module screens claimed Lead/Rhythm note groups for that ambiguity and
marks every member of a two-or-more-note group as unresolved, rather than
silently promoting each member as if it had been independently confirmed in
isolation. No module anywhere in this codebase currently performs real
per-pitch audio isolation (every existing evidence module reports
``source_isolation_proven=False``), so the fail-closed default here is
always "ambiguous, review-required" for an actual chord -- never a positive
isolation claim. A genuinely monophonic claimed note is unaffected.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from pathlib import Path

from .bass_attack_evidence import MAX_DELAY_SECONDS
from .guitar_onset_oracle import (
    GUITAR_ONSET_ORACLE_ROLES,
    GuitarAttackEvidence,
    inspect_guitar_attack_onset,
)

# Claimed onsets at or inside this spacing share one physical pick/strum
# attack for the purpose of this screen. Reuse the bounded onset-delay
# tolerance already proven for a single note's attack evidence
# (bass_attack_evidence.MAX_DELAY_SECONDS) rather than invent a new constant.
CHORD_ONSET_TOLERANCE_SECONDS = MAX_DELAY_SECONDS


@dataclass(frozen=True)
class ChordScreenedOnset:
    """One claimed note's attack evidence plus its chord-ambiguity screen."""

    evidence: GuitarAttackEvidence
    chord_group_size: int
    chord_ambiguous: bool

    def __post_init__(self) -> None:
        if self.chord_group_size < 1:
            raise ValueError("INVALID_CHORD_GROUP_SIZE")
        if self.chord_ambiguous and self.chord_group_size < 2:
            raise ValueError("INVALID_CHORD_AMBIGUOUS_SINGLE_NOTE_GROUP")

    @property
    def independently_verified(self) -> bool:
        """Chord membership vetoes promotion even when the shared attack measured well.

        A monophonic claimed note (group size 1) is promoted exactly as the
        underlying oracle already proves it; this screen never *adds*
        confidence, only removes it from an unresolved chord member.
        """
        return self.evidence.independent_attack and not self.chord_ambiguous


def screen_guitar_chord_onset_ambiguity(
    role: str,
    audio_path: Path,
    note_events: Sequence[tuple[float, float]],
) -> tuple[ChordScreenedOnset, ...]:
    """Screen claimed Lead/Rhythm note onsets for unresolved chord ambiguity.

    ``note_events`` is a sequence of ``(note_start_seconds,
    note_duration_seconds)`` pairs for one role's candidate chart, in any
    order. Results are returned in the same order and count as the input.
    Two or more claimed notes whose start times fall within
    ``CHORD_ONSET_TOLERANCE_SECONDS`` of the earliest member of their group
    are a chord: every member is independently measured via the existing
    onset oracle, but each is additionally marked ``chord_ambiguous`` and
    cannot be independently verified through this screen regardless of how
    strongly its own (shared) attack measured. A duplicate exact-time claim
    is a degenerate chord of size >= 2, not rejected input: real Lead/Rhythm
    arrangements legitimately strike multiple strings at once.

    Grouping anchors each group to its earliest member's start time (not a
    rolling chain to the previous member), so a slow strum or arpeggio spread
    across several multiples of the tolerance window is not transitively
    collapsed into one group just because consecutive gaps are each small.
    """
    if role not in GUITAR_ONSET_ORACLE_ROLES:
        raise ValueError("INVALID_GUITAR_ONSET_ORACLE_ROLE")
    note_events = tuple(note_events)
    for start_seconds, duration_seconds in note_events:
        if (
            type(start_seconds) not in (int, float)
            or type(duration_seconds) not in (int, float)
            or not isfinite(start_seconds)
            or not isfinite(duration_seconds)
            or start_seconds < 0
            or duration_seconds <= 0
        ):
            raise ValueError("INVALID_GUITAR_ATTACK_ONSET_ARGUMENT")

    order = sorted(range(len(note_events)), key=lambda i: note_events[i][0])
    groups: list[list[int]] = []
    anchor_start = None
    for i in order:
        start_seconds = note_events[i][0]
        if (
            groups
            and anchor_start is not None
            and start_seconds - anchor_start <= CHORD_ONSET_TOLERANCE_SECONDS
        ):
            groups[-1].append(i)
        else:
            groups.append([i])
            anchor_start = start_seconds

    results: list[ChordScreenedOnset | None] = [None] * len(note_events)
    for group in groups:
        chord_ambiguous = len(group) >= 2
        for i in group:
            start_seconds, duration_seconds = note_events[i]
            evidence = inspect_guitar_attack_onset(
                role, audio_path,
                note_start_seconds=start_seconds, note_duration_seconds=duration_seconds,
            )
            results[i] = ChordScreenedOnset(evidence, len(group), chord_ambiguous)
    return tuple(results)
