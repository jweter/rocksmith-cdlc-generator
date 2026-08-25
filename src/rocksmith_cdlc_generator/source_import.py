from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class SourceTrustClass(str, Enum):
    symbolic_unverified = "symbolic_unverified"
    symbolic_verified = "symbolic_verified"
    audio_derived = "audio_derived"
    user_confirmed = "user_confirmed"


class SourceProvenance(BaseModel):
    source_type: str
    source_filename: str
    source_sha256: str
    importer: str
    importer_version: str


class SourceTempoEvent(BaseModel):
    tick: int = Field(ge=0)
    time_seconds: float = Field(ge=0)
    bpm: float = Field(gt=0)


class SourceTimeSignatureEvent(BaseModel):
    tick: int = Field(ge=0)
    time_seconds: float = Field(ge=0)
    numerator: int = Field(gt=0)
    denominator: int = Field(gt=0)


class SourceNoteEvent(BaseModel):
    start_seconds: float = Field(ge=0)
    duration_seconds: float = Field(gt=0)
    midi: int = Field(ge=0, le=127)
    note_name: str | None = None
    string_index: int | None = Field(default=None, ge=0)
    fret: int | None = Field(default=None, ge=0)
    techniques: list[str] = Field(default_factory=list)
    import_confidence: float = Field(ge=0, le=1)
    trust_class: SourceTrustClass = SourceTrustClass.symbolic_unverified
    review_required: bool = False
    composition_source_track_index: int | None = Field(default=None, ge=0)
    composition_source_event_index: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def composition_origin_is_complete(self) -> "SourceNoteEvent":
        fields = (
            self.composition_source_track_index,
            self.composition_source_event_index,
        )
        if (fields[0] is None) != (fields[1] is None):
            raise ValueError(
                "composed source-note origin requires both track and event indexes"
            )
        return self


class SourceTrack(BaseModel):
    source_track_index: int = Field(ge=0)
    name: str | None = None
    instrument: str
    channel_numbers: list[int] = Field(default_factory=list)
    program_numbers: list[int] = Field(default_factory=list)
    tuning_midi: list[int] | None = None
    notes: list[SourceNoteEvent]

    @model_validator(mode="after")
    def notes_are_ordered(self) -> "SourceTrack":
        starts = [note.start_seconds for note in self.notes]
        if starts != sorted(starts):
            raise ValueError("source track notes must be ordered by start time")
        return self


class ImportedSource(BaseModel):
    schema_version: int = 1
    provenance: SourceProvenance
    ticks_per_beat: int | None = Field(default=None, gt=0)
    tempo_events: list[SourceTempoEvent] = Field(default_factory=list)
    time_signatures: list[SourceTimeSignatureEvent] = Field(default_factory=list)
    beat_times_seconds: list[float] = Field(default_factory=list)
    tracks: list[SourceTrack]
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def beat_grid_is_ordered(self) -> "ImportedSource":
        if any(time < 0 for time in self.beat_times_seconds):
            raise ValueError("source beat times must be non-negative")
        if any(current <= previous for previous, current in zip(self.beat_times_seconds, self.beat_times_seconds[1:])):
            raise ValueError("source beat times must be strictly increasing")
        return self

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return path

    @classmethod
    def read_json(cls, path: Path) -> "ImportedSource":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
