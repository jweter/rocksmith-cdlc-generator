"""Independent PCM onset oracle for Lead and Rhythm guitar events (#796 slices 40/41).

Lead and Rhythm are distinct role-specific sources (slice 35); this module
does not conflate them with each other or with Bass. It reuses the same
measured-energy-transition primitive already proven for Bass
(``bass_attack_evidence._measure_attack_onset``) so both non-Bass roles get
the identical independent-evidence contract: a claimed note onset is
corroborated only by a local PCM energy transition, never by an estimator's
own confidence.

This module is an oracle over claimed onsets, not a reconciliation/promotion
pipeline. It does not isolate a guitar from a mix, verify pitch, or produce
a Rocksmith gameplay PASS.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

from .bass_attack_evidence import (
    MAX_DELAY_SECONDS,
    MIN_ATTACK_CONFIDENCE,
    _measure_attack_onset,
)

GUITAR_ONSET_ORACLE_ROLES = ("lead", "rhythm")


@dataclass(frozen=True)
class GuitarAttackEvidence:
    """Per-event independent PCM onset evidence for one Lead or Rhythm note."""

    role: str  # "lead" or "rhythm"; never "bass"
    status: str  # attack_detected, no_attack, insufficient_signal, unavailable
    confidence: float = 0.0
    measured_onset_delta_seconds: float | None = None
    pre_attack_rms: float | None = None
    post_attack_rms: float | None = None
    source_isolation_proven: bool = False
    pitch_verified: bool = False
    recording_clock_verified: bool = False
    musical_pass_proven: bool = False

    def __post_init__(self) -> None:
        if self.role not in GUITAR_ONSET_ORACLE_ROLES:
            raise ValueError("GuitarAttackEvidence role must be 'lead' or 'rhythm'")

    @property
    def independent_attack(self) -> bool:
        return (
            self.status == "attack_detected"
            and self.confidence >= MIN_ATTACK_CONFIDENCE
            and self.measured_onset_delta_seconds is not None
            and 0 <= self.measured_onset_delta_seconds <= MAX_DELAY_SECONDS
        )


@dataclass(frozen=True)
class GuitarOnsetOracleReport:
    """Whether a role's claimed first and later events hold independent evidence."""

    role: str
    events: tuple[GuitarAttackEvidence, ...]

    @property
    def verified_event_count(self) -> int:
        return sum(1 for event in self.events if event.independent_attack)

    @property
    def unverified_event_count(self) -> int:
        return len(self.events) - self.verified_event_count

    @property
    def first_event_verified(self) -> bool:
        return bool(self.events) and self.events[0].independent_attack

    @property
    def later_events_verified(self) -> bool:
        later = self.events[1:]
        return bool(later) and all(event.independent_attack for event in later)


def inspect_guitar_attack_onset(
    role: str, audio_path: Path, *, note_start_seconds: float, note_duration_seconds: float,
) -> GuitarAttackEvidence:
    """Measure one Lead/Rhythm candidate onset against local stem PCM.

    Same bounded 16-bit-PCM, no-model, no-remote-I/O contract as Bass; the
    result proves only a measured local energy transition near the claimed
    onset, never guitar-role isolation, pitch correctness or gameplay PASS.
    """
    if role not in GUITAR_ONSET_ORACLE_ROLES:
        raise ValueError("INVALID_GUITAR_ONSET_ORACLE_ROLE")
    try:
        raw = _measure_attack_onset(
            audio_path,
            note_start_seconds=note_start_seconds,
            note_duration_seconds=note_duration_seconds,
        )
    except ValueError as exc:
        raise ValueError("INVALID_GUITAR_ATTACK_ONSET_ARGUMENT") from exc
    return GuitarAttackEvidence(
        role, raw.status, raw.confidence, raw.measured_onset_delta_seconds,
        raw.pre_attack_rms, raw.post_attack_rms,
    )


def inspect_guitar_onset_oracle(
    role: str,
    audio_path: Path,
    note_events: Sequence[tuple[float, float]],
) -> GuitarOnsetOracleReport:
    """Independently screen a role's first and later claimed onsets.

    ``note_events`` is an ordered sequence of ``(note_start_seconds,
    note_duration_seconds)`` for the candidate chart under review, strictly
    increasing by start time with no duplicate onset. Each event is measured
    independently from local stem PCM; a chart is not promoted to
    recording-clock truth merely because its first event measures well while
    later events do not, or vice versa. Unsorted or duplicate-time input is
    rejected rather than silently relabeling which event is "first".
    """
    if role not in GUITAR_ONSET_ORACLE_ROLES:
        raise ValueError("INVALID_GUITAR_ONSET_ORACLE_ROLE")
    note_events = tuple(note_events)
    starts = [start_seconds for start_seconds, _ in note_events]
    if any(earlier >= later for earlier, later in pairwise(starts)):
        raise ValueError("INVALID_GUITAR_ONSET_ORACLE_SEQUENCE_NOT_STRICTLY_ORDERED")
    events = tuple(
        inspect_guitar_attack_onset(
            role, audio_path,
            note_start_seconds=start_seconds, note_duration_seconds=duration_seconds,
        )
        for start_seconds, duration_seconds in note_events
    )
    return GuitarOnsetOracleReport(role, events)
