from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .reviewed_techniques import SUPPORTED_TECHNIQUES
from .source_import import ImportedSource, SourceTrack

_SUPPORTED_TECHNIQUE_SET = frozenset(SUPPORTED_TECHNIQUES)

EOFCompatibilityField = Literal[
    "note_count",
    "tuning_midi",
    "note_midi",
    "note_position",
    "note_timing",
    "note_techniques",
]


class EOFReferenceNote(BaseModel):
    """One independently reviewed EOF observation for a synthetic/source-bound event."""

    model_config = ConfigDict(frozen=True)

    event_index: int = Field(ge=0)
    start_seconds: float = Field(ge=0)
    duration_seconds: float = Field(gt=0)
    midi: int = Field(ge=0, le=127)
    string_index: int = Field(ge=0)
    fret: int = Field(ge=0)
    techniques: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def techniques_are_supported(self) -> "EOFReferenceNote":
        normalized = sorted({item.strip().lower() for item in self.techniques if item.strip()})
        unsupported = [item for item in normalized if item not in _SUPPORTED_TECHNIQUE_SET]
        if unsupported:
            raise ValueError(
                "EOF compatibility fixtures may contain only project-supported techniques: "
                + ", ".join(unsupported)
            )
        object.__setattr__(self, "techniques", normalized)
        return self


class EOFCompatibilityFixture(BaseModel):
    """Source-bound, human-reviewed EOF observations that never become chart authority."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    fixture_id: str = Field(min_length=1)
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_format: Literal["gp3", "gp4", "gp5"]
    source_track_index: int = Field(ge=0)
    eof_version: str = Field(min_length=1)
    evidence_note: str = Field(min_length=1)
    tuning_midi: list[int] = Field(min_length=1)
    notes: list[EOFReferenceNote] = Field(default_factory=list)

    @model_validator(mode="after")
    def event_indices_are_contiguous(self) -> "EOFCompatibilityFixture":
        indices = [note.event_index for note in self.notes]
        if indices != list(range(len(indices))):
            raise ValueError("EOF compatibility fixture event indices must be contiguous from zero")
        return self

    @classmethod
    def read_json(cls, path: Path) -> "EOFCompatibilityFixture":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


class EOFCompatibilityMismatch(BaseModel):
    model_config = ConfigDict(frozen=True)

    field: EOFCompatibilityField
    event_index: int | None = Field(default=None, ge=0)
    expected: str
    actual: str


class EOFCompatibilityReport(BaseModel):
    """Read-only discrepancy report between one imported track and reviewed EOF evidence."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    fixture_id: str
    score_sha256: str
    source_track_index: int
    timing_tolerance_seconds: float = Field(ge=0)
    mismatches: list[EOFCompatibilityMismatch] = Field(default_factory=list)

    @property
    def matched(self) -> bool:
        return not self.mismatches


def _track_for_fixture(source: ImportedSource, fixture: EOFCompatibilityFixture) -> SourceTrack:
    if source.provenance.source_sha256 != fixture.score_sha256:
        raise ValueError("EOF compatibility fixture is stale or belongs to a different score")
    if source.provenance.source_type != fixture.score_format:
        raise ValueError("EOF compatibility fixture score format does not match imported score")
    track = next(
        (item for item in source.tracks if item.source_track_index == fixture.source_track_index),
        None,
    )
    if track is None:
        raise ValueError("EOF compatibility fixture source track is not present in imported score")
    return track


def _supported_techniques(values: list[str]) -> list[str]:
    return sorted({value.strip().lower() for value in values if value.strip().lower() in _SUPPORTED_TECHNIQUE_SET})


def compare_imported_source_to_eof_fixture(
    source: ImportedSource,
    fixture: EOFCompatibilityFixture,
    *,
    timing_tolerance_seconds: float = 1e-6,
) -> EOFCompatibilityReport:
    """Compare deterministic importer output with independently reviewed EOF observations.

    The comparison is evidence-only. It never mutates imported data, accepts source
    mappings, rewrites positions/timing/techniques, or promotes EOF to canonical authority.
    """

    if timing_tolerance_seconds < 0:
        raise ValueError("timing tolerance must be non-negative")
    track = _track_for_fixture(source, fixture)
    mismatches: list[EOFCompatibilityMismatch] = []

    actual_tuning = list(track.tuning_midi or [])
    if actual_tuning != fixture.tuning_midi:
        mismatches.append(
            EOFCompatibilityMismatch(
                field="tuning_midi",
                expected=repr(fixture.tuning_midi),
                actual=repr(actual_tuning),
            )
        )

    if len(track.notes) != len(fixture.notes):
        mismatches.append(
            EOFCompatibilityMismatch(
                field="note_count",
                expected=str(len(fixture.notes)),
                actual=str(len(track.notes)),
            )
        )

    for expected, actual in zip(fixture.notes, track.notes):
        index = expected.event_index
        if actual.midi != expected.midi:
            mismatches.append(
                EOFCompatibilityMismatch(
                    field="note_midi",
                    event_index=index,
                    expected=str(expected.midi),
                    actual=str(actual.midi),
                )
            )

        actual_position = (actual.string_index, actual.fret)
        expected_position = (expected.string_index, expected.fret)
        if actual_position != expected_position:
            mismatches.append(
                EOFCompatibilityMismatch(
                    field="note_position",
                    event_index=index,
                    expected=repr(expected_position),
                    actual=repr(actual_position),
                )
            )

        onset_delta = abs(actual.start_seconds - expected.start_seconds)
        duration_delta = abs(actual.duration_seconds - expected.duration_seconds)
        if onset_delta > timing_tolerance_seconds or duration_delta > timing_tolerance_seconds:
            mismatches.append(
                EOFCompatibilityMismatch(
                    field="note_timing",
                    event_index=index,
                    expected=f"{expected.start_seconds:.9f}/{expected.duration_seconds:.9f}",
                    actual=f"{actual.start_seconds:.9f}/{actual.duration_seconds:.9f}",
                )
            )

        actual_techniques = _supported_techniques(actual.techniques)
        if actual_techniques != expected.techniques:
            mismatches.append(
                EOFCompatibilityMismatch(
                    field="note_techniques",
                    event_index=index,
                    expected=repr(expected.techniques),
                    actual=repr(actual_techniques),
                )
            )

    return EOFCompatibilityReport(
        fixture_id=fixture.fixture_id,
        score_sha256=fixture.score_sha256,
        source_track_index=fixture.source_track_index,
        timing_tolerance_seconds=timing_tolerance_seconds,
        mismatches=mismatches,
    )
