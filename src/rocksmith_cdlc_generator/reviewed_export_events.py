from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .hashing import sha256_file
from .reviewed_arrangement_timing import ReviewedArrangementTiming, _reviewed_arrangement_timing_locked
from .reviewed_chords import reviewed_chord_groups as _reviewed_chord_groups
from .reviewed_timing_transform import map_reviewed_source_interval, map_reviewed_source_time
from .score_mapping_review import score_mapping_transaction
from .score_source import ArrangementRole
from .shared_timeline import _safe_project_file
from .source_import import ImportedSource, SourceBendPoint, SourceNoteEvent, SourceTrustClass


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
    bend_points: list[SourceBendPoint] = Field(default_factory=list)
    slide_target_fret: int | None = Field(default=None, ge=0)
    link_next: bool = False
    import_confidence: float = Field(ge=0, le=1)
    trust_class: SourceTrustClass
    review_required: bool = False
    position_ready: bool
    composition_source_track_index: int | None = Field(default=None, ge=0)
    composition_source_event_index: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def composition_origin_is_complete(self) -> "ReviewedExportNote":
        fields = (
            self.composition_source_track_index,
            self.composition_source_event_index,
        )
        if (fields[0] is None) != (fields[1] is None):
            raise ValueError(
                "reviewed composed-note origin requires both track and event indexes"
            )
        return self


class ReviewedExportChordGroup(BaseModel):
    """Explicit human-reviewed chord identity preserved by source-event index."""

    model_config = ConfigDict(frozen=True)

    source_event_indices: list[int] = Field(min_length=2)

    @model_validator(mode="after")
    def members_are_unique_and_ordered(self) -> "ReviewedExportChordGroup":
        if self.source_event_indices != sorted(self.source_event_indices):
            raise ValueError("reviewed export chord members must remain ordered")
        if len(self.source_event_indices) != len(set(self.source_event_indices)):
            raise ValueError("reviewed export chord contains duplicate source events")
        return self


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
    chord_groups: list[ReviewedExportChordGroup] = Field(default_factory=list)
    human_confirmed_timing: Literal[True] = True

    @model_validator(mode="after")
    def notes_and_chords_are_consistent(self) -> "ReviewedExportArrangement":
        source_starts = [note.source_start_seconds for note in self.notes]
        reviewed_starts = [note.reviewed_start_seconds for note in self.notes]
        if source_starts != sorted(source_starts):
            raise ValueError("reviewed export source notes must remain ordered")
        if reviewed_starts != sorted(reviewed_starts):
            raise ValueError("reviewed export notes must remain ordered after timing projection")
        if self.role is ArrangementRole.bass and self.chord_groups:
            raise ValueError("reviewed Bass export cannot carry guitar chord groups")

        known = {note.source_event_index for note in self.notes}
        used: set[int] = set()
        for group in self.chord_groups:
            members = set(group.source_event_indices)
            if not members.issubset(known):
                raise ValueError("reviewed export chord references an unknown source event")
            if used.intersection(members):
                raise ValueError("one reviewed export source event cannot belong to multiple chords")
            used.update(members)
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


def _project_bend_points(
    timing: ReviewedArrangementTiming,
    note: SourceNoteEvent,
    reviewed_start_seconds: float,
    reviewed_duration_seconds: float,
) -> list[SourceBendPoint]:
    """Rebase each bend point onto the reviewed note interval from its own source time.

    ``SourceBendPoint.position`` is a fraction of the note's own duration. Reusing that
    fraction unchanged against a retimed reviewed duration is only correct if reviewed
    timing scales this note uniformly; the promoted timing transform is piecewise linear
    and can bend the mapping within a single note's span. Each point is therefore resolved
    to its absolute source timestamp, mapped through the same reviewed timing curve as the
    note's own endpoints, and rebased as a fraction of the reviewed interval.
    """

    projected: list[SourceBendPoint] = []
    for point in note.bend_points:
        source_time = note.start_seconds + point.position * note.duration_seconds
        reviewed_time = map_reviewed_source_time(timing, source_time)
        fraction = (reviewed_time - reviewed_start_seconds) / reviewed_duration_seconds
        projected.append(point.model_copy(update={"position": min(1.0, max(0.0, fraction))}))
    return projected


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
                bend_points=_project_bend_points(timing, note, reviewed_start, reviewed_duration),
                slide_target_fret=note.slide_target_fret,
                link_next=note.link_next,
                import_confidence=note.import_confidence,
                trust_class=note.trust_class,
                review_required=note.review_required,
                position_ready=note.string_index is not None and note.fret is not None,
                composition_source_track_index=note.composition_source_track_index,
                composition_source_event_index=note.composition_source_event_index,
            )
        )
    return projected


def _project_chord_groups_locked(
    project: Path,
    timing: ReviewedArrangementTiming,
) -> list[ReviewedExportChordGroup]:
    if timing.role is ArrangementRole.bass:
        return []
    groups = _reviewed_chord_groups(
        project,
        arrangement=timing.role.value,
        source_track_index=timing.source_track_index,
    )
    return [ReviewedExportChordGroup(source_event_indices=list(group)) for group in groups]


def reviewed_export_arrangement(project_dir: Path, role: ArrangementRole) -> ReviewedExportArrangement:
    """Build an export-ready read model using only current promoted reviewed authority.

    Timing authority validation, arrangement projection, fan-out verification, source read,
    note mapping, and explicit Lead/Rhythm chord membership are read while the score
    transaction lock is held. It writes no review or authoring authority, though resolving
    a current multi-track Lead/Rhythm selection may refresh its deterministic composed-
    source cache. It does not bypass chart validation, XML export, source acceptance,
    chord review, or packaging gates.
    """

    project = project_dir.expanduser().resolve()
    with score_mapping_transaction(project):
        timing = _reviewed_arrangement_timing_locked(project, role)
        source = _load_current_source_locked(project, timing)
        track = source.tracks[0]
        notes = _project_notes(source, timing)
        chord_groups = _project_chord_groups_locked(project, timing)
        return ReviewedExportArrangement(
            role=role,
            source_track_index=timing.source_track_index,
            source_output_json=timing.source_output_json,
            source_output_sha256=timing.source_output_sha256,
            recording_sha256=timing.recording_sha256,
            score_sha256=timing.score_sha256,
            tuning_midi=None if track.tuning_midi is None else tuple(track.tuning_midi),
            notes=notes,
            chord_groups=chord_groups,
            human_confirmed_timing=True,
        )
