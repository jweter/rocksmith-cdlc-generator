from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Sequence

from rocksmith_cdlc_generator.eof_parity_fixture import EofParityFixture, EofParityNote


@dataclass(frozen=True)
class EofParityMismatch:
    field: str
    expected: object
    actual: object


@dataclass(frozen=True)
class EofParityDifferential:
    fixture_id: str
    arrangement: str
    matches: bool
    mismatches: tuple[EofParityMismatch, ...]


def _close(expected: float, actual: float, *, tolerance_seconds: float) -> bool:
    return isfinite(actual) and abs(expected - actual) <= tolerance_seconds


def _compare_note(
    expected: EofParityNote,
    actual: EofParityNote,
    *,
    index: int,
    tolerance_seconds: float,
) -> list[EofParityMismatch]:
    mismatches: list[EofParityMismatch] = []
    prefix = f"notes[{index}]"
    if not _close(expected.onset_seconds, actual.onset_seconds, tolerance_seconds=tolerance_seconds):
        mismatches.append(EofParityMismatch(f"{prefix}.onset_seconds", expected.onset_seconds, actual.onset_seconds))
    if not _close(expected.duration_seconds, actual.duration_seconds, tolerance_seconds=tolerance_seconds):
        mismatches.append(
            EofParityMismatch(f"{prefix}.duration_seconds", expected.duration_seconds, actual.duration_seconds)
        )
    if expected.string != actual.string:
        mismatches.append(EofParityMismatch(f"{prefix}.string", expected.string, actual.string))
    if expected.fret != actual.fret:
        mismatches.append(EofParityMismatch(f"{prefix}.fret", expected.fret, actual.fret))
    if expected.techniques != actual.techniques:
        mismatches.append(EofParityMismatch(f"{prefix}.techniques", expected.techniques, actual.techniques))
    return mismatches


def compare_eof_parity_fixtures(
    expected: EofParityFixture,
    actual: EofParityFixture,
    *,
    tolerance_seconds: float = 1e-6,
) -> EofParityDifferential:
    """Compare two media-safe EOF parity fixtures deterministically.

    ``expected`` is the reference/oracle metadata and ``actual`` is generator
    output projected into the same repository-safe contract. The comparison is
    deliberately exact for musical identity and bounded only for floating-point
    timing representation. It never infers human musical acceptance.
    """

    if not isfinite(tolerance_seconds) or tolerance_seconds < 0:
        raise ValueError("tolerance_seconds must be finite and non-negative")

    mismatches: list[EofParityMismatch] = []
    if expected.schema_version != actual.schema_version:
        mismatches.append(EofParityMismatch("schema_version", expected.schema_version, actual.schema_version))
    if expected.fixture_id != actual.fixture_id:
        mismatches.append(EofParityMismatch("fixture_id", expected.fixture_id, actual.fixture_id))
    if expected.source_kind != actual.source_kind:
        mismatches.append(EofParityMismatch("source_kind", expected.source_kind, actual.source_kind))
    if expected.arrangement != actual.arrangement:
        mismatches.append(EofParityMismatch("arrangement", expected.arrangement, actual.arrangement))

    if len(expected.beat_times_seconds) != len(actual.beat_times_seconds):
        mismatches.append(
            EofParityMismatch("beat_times_seconds.length", len(expected.beat_times_seconds), len(actual.beat_times_seconds))
        )
    for index, (expected_beat, actual_beat) in enumerate(
        zip(expected.beat_times_seconds, actual.beat_times_seconds, strict=False)
    ):
        if not _close(expected_beat, actual_beat, tolerance_seconds=tolerance_seconds):
            mismatches.append(EofParityMismatch(f"beat_times_seconds[{index}]", expected_beat, actual_beat))

    if len(expected.notes) != len(actual.notes):
        mismatches.append(EofParityMismatch("notes.length", len(expected.notes), len(actual.notes)))
    for index, (expected_note, actual_note) in enumerate(zip(expected.notes, actual.notes, strict=False)):
        mismatches.extend(
            _compare_note(expected_note, actual_note, index=index, tolerance_seconds=tolerance_seconds)
        )

    return EofParityDifferential(
        fixture_id=expected.fixture_id,
        arrangement=expected.arrangement,
        matches=not mismatches,
        mismatches=tuple(mismatches),
    )
