from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .hashing import sha256_file
from .reviewed_arrangement_timing import ReviewedArrangementTiming, _reviewed_arrangement_timing_locked
from .reviewed_timing_transform import map_reviewed_source_interval
from .score_mapping_review import score_mapping_transaction
from .score_source import ArrangementRole
from .shared_timeline import _safe_project_file
from .source_import import ImportedSource, SourceTrustClass


class ReviewedExportNote(BaseModel):
    """One source note projected onto the promoted human-reviewed song timing."""

    model_config = ConfigDict(frozen=True)

    source_event_index: int = Field(ge=0)
    source_start_seconds: float = Field(ge=0)
    source_duration_seconds: float = Field(gt=0)
    reviewed_start_seconds: float = Field(ge=0)
    reviewed_duration_seconds: float = Field(gt=0)
    midi: int = Field(ge=0, le=127)
    note_name: str | None = None
    string_index: int | None = Field(default=None, ge=0)
    fret: int | None = Field(default=None, ge=0)
    techniques: list[str] = Field(default_factory=list)
    import_confidence: float = Field(ge=0, le=1)
    trust_class: SourceTrustClass
    review_required: bool = False
    position_ready: bool


class ReviewedExportArrangement(BaseModel):
    """Read-only export-consumer view of one confirmed arrangement under reviewed timing."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    role: ArrangementRole
    source_track_index: int = Field(ge=0)
    source_output_json: str
    source_output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    recording_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tuning_midi: tuple[int, ...] | None = None
    notes: list[ReviewedExportNote]
    human_confirmed_timing: Literal[True] = True

    @model_validator(mode="after")
    def notes_are_ordered(self) -> "ReviewedExportArrangement":
        source_starts = [note.source_start_seconds for note in self.notes]
        reviewed_starts = [note.reviewed_start_seconds for note in self.notes]
        if source_starts != sorted(source_starts):
            raise ValueError("reviewed export source notes must remain ordered")
        if reviewed_starts != sorted(reviewed_starts):
            raise ValueError("reviewed export notes must remain ordered after timing projection")
        return self


def _load_current_source_locked(project: Path, timing: ReviewedArrangementTiming) -> ImportedSource:
    output = _safe_project_file(project, timing.source_output_json)
    if sha256_file(output) != timing.source_output_sha256:
        raise ValueError(f"{timing.role.value} fan-out output content changed after timing projection")

    source = ImportedSource.read_json(output)
    if source.provenance.source_sha256 != timing.score_sha256:
        raise ValueError(f"{timing.role.value} fan-out source provenance does not match reviewed score timing")
    if len(source.tracks) != 1:
        raise ValueError(f"{timing.role.value} fan-out output must contain exactly one track")
    track = source.tracks[0]
    if track.source_track_index != timing.source_track_index or track.instrument != timing.role.value:
        raise ValueError(f"{timing.role.value} fan-out track does not match reviewed arrangement timing")
    return source


def _project_notes(source: ImportedSource, timing: ReviewedArrangementTiming) -> list[ReviewedExportNote]:
    track = source.tracks[0]
    projected: list[ReviewedExportNote] = []
    for event_index, note in enumerate(track.notes):
        reviewed_start, reviewed_duration = map_reviewed_source_interval(
            timing,
            note.start_seconds,
            note.duration_seconds,
        )
        projected.append(
            ReviewedExportNote(
                source_event_index=event_index,
                source_start_seconds=note.start_seconds,
                source_duration_seconds=note.duration_seconds,
                reviewed_start_seconds=reviewed_start,
                reviewed_duration_seconds=reviewed_duration,
                midi=note.midi,
                note_name=note.note_name,
                string_index=note.string_index,
                fret=note.fret,
                techniques=list(note.techniques),
                import_confidence=note.import_confidence,
                trust_class=note.trust_class,
                review_required=note.review_required,
                position_ready=note.string_index is not None and note.fret is not None,
            )
        )
    return projected


def reviewed_export_arrangement(project_dir: Path, role: ArrangementRole) -> ReviewedExportArrangement:
    """Build an export-ready read model using only current promoted reviewed timing.

    Timing authority validation, arrangement projection, fan-out verification, source read,
    and note mapping are serialized under the score transaction lock. This function writes
    nothing and does not bypass chart validation, XML export, source acceptance, or packaging
    gates.
    """

    project = project_dir.expanduser().resolve()
    with score_mapping_transaction(project):
        timing = _reviewed_arrangement_timing_locked(project, role)
        source = _load_current_source_locked(project, timing)
        track = source.tracks[0]
        notes = _project_notes(source, timing)
        return ReviewedExportArrangement(
            role=role,
            source_track_index=timing.source_track_index,
            source_output_json=timing.source_output_json,
            source_output_sha256=timing.source_output_sha256,
            recording_sha256=timing.recording_sha256,
            score_sha256=timing.score_sha256,
            tuning_midi=None if track.tuning_midi is None else tuple(track.tuning_midi),
            notes=notes,
            human_confirmed_timing=True,
        )
