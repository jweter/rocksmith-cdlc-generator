from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .source_import import ImportedSource


class EOFHandPositionObservation(BaseModel):
    """One manually reviewed EOF fret-hand-position marker.

    This is external reference evidence only. ``fret`` records what EOF displayed at
    ``start_seconds``; it is not an accepted Rocksmith fingering or optimizer target.
    ``source_event_index`` is optional because an EOF marker may be observed between
    imported note events.
    """

    model_config = ConfigDict(frozen=True)

    start_seconds: float = Field(ge=0)
    fret: int = Field(ge=0, le=30)
    source_event_index: int | None = Field(default=None, ge=0)


class EOFHandPositionFixture(BaseModel):
    """Source-bound EOF fret-hand-position observations with no chart authority."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    fixture_id: str = Field(min_length=1)
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_format: Literal["gp3", "gp4", "gp5"]
    source_track_index: int = Field(ge=0)
    eof_version: str = Field(min_length=1)
    evidence_note: str = Field(min_length=1)
    observations: list[EOFHandPositionObservation] = Field(default_factory=list)

    @model_validator(mode="after")
    def observations_are_strictly_ordered(self) -> "EOFHandPositionFixture":
        times = [item.start_seconds for item in self.observations]
        if any(right <= left for left, right in zip(times, times[1:])):
            raise ValueError(
                "EOF hand-position observations must use strictly increasing start times"
            )
        return self

    @classmethod
    def read_json(cls, path: Path) -> "EOFHandPositionFixture":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


class EOFHandPositionEvidenceStatus(BaseModel):
    """Validated identity summary for advisory EOF hand-position evidence."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    fixture_id: str
    score_sha256: str
    source_track_index: int
    observation_count: int = Field(ge=0)


def validate_eof_hand_position_fixture(
    source: ImportedSource,
    fixture: EOFHandPositionFixture,
) -> EOFHandPositionEvidenceStatus:
    """Fail closed unless EOF hand-position evidence matches one imported source track.

    Validation establishes only that the observation record belongs to the same score
    and source-track identity and that any optional event references still exist. It
    does not compare, select, accept, or rewrite string/fret positions and does not
    define an optimizer cost model.
    """

    if source.provenance.source_sha256 != fixture.score_sha256:
        raise ValueError("EOF hand-position fixture is stale or belongs to a different score")
    if source.provenance.source_type != fixture.score_format:
        raise ValueError("EOF hand-position fixture score format does not match imported score")

    track = next(
        (item for item in source.tracks if item.source_track_index == fixture.source_track_index),
        None,
    )
    if track is None:
        raise ValueError("EOF hand-position fixture source track is not present in imported score")

    for observation in fixture.observations:
        event_index = observation.source_event_index
        if event_index is not None and event_index >= len(track.notes):
            raise ValueError(
                "EOF hand-position fixture references a source event that no longer exists"
            )

    return EOFHandPositionEvidenceStatus(
        fixture_id=fixture.fixture_id,
        score_sha256=fixture.score_sha256,
        source_track_index=fixture.source_track_index,
        observation_count=len(fixture.observations),
    )
