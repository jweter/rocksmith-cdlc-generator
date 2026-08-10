from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .alignment import AlignmentReport, map_source_time
from .source_import import ImportedSource, SourceNoteEvent, SourceTrustClass

GuitarArrangement = Literal["lead", "rhythm"]


class GuitarAuthoringNote(BaseModel):
    start_seconds: float = Field(ge=0)
    duration_seconds: float = Field(gt=0)
    midi: int = Field(ge=0, le=127)
    string_index: int = Field(ge=0, le=5)
    fret: int = Field(ge=0)
    techniques: list[str] = Field(default_factory=list)
    trust_class: SourceTrustClass
    review_required: bool = False


class GuitarChordEvent(BaseModel):
    start_seconds: float = Field(ge=0)
    sustain_seconds: float = Field(gt=0)
    chord_id: int = Field(ge=0)
    shape: tuple[int, int, int, int, int, int]
    notes: list[GuitarAuthoringNote]
    review_required: bool = False

    @model_validator(mode="after")
    def unique_strings(self) -> "GuitarChordEvent":
        strings = [note.string_index for note in self.notes]
        if len(strings) < 2:
            raise ValueError("guitar chord requires at least two notes")
        if len(strings) != len(set(strings)):
            raise ValueError("guitar chord cannot contain multiple notes on one string")
        return self


class UnresolvedGuitarNote(BaseModel):
    source_start_seconds: float = Field(ge=0)
    midi: int = Field(ge=0, le=127)
    reason: str


class GuitarAuthoringChart(BaseModel):
    schema_version: int = 1
    arrangement: GuitarArrangement
    source_sha256: str
    alignment_confidence: float = Field(ge=0, le=1)
    tuning_midi: tuple[int, int, int, int, int, int]
    single_notes: list[GuitarAuthoringNote] = Field(default_factory=list)
    chords: list[GuitarChordEvent] = Field(default_factory=list)
    unresolved_notes: list[UnresolvedGuitarNote] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def events_are_ordered(self) -> "GuitarAuthoringChart":
        if any(b.start_seconds < a.start_seconds for a, b in zip(self.single_notes, self.single_notes[1:])):
            raise ValueError("guitar single notes must be sorted")
        if any(b.start_seconds < a.start_seconds for a, b in zip(self.chords, self.chords[1:])):
            raise ValueError("guitar chords must be sorted")
        return self

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return path


def _mapped_note(
    source_note: SourceNoteEvent,
    *,
    tuning: tuple[int, int, int, int, int, int],
    alignment: AlignmentReport,
) -> tuple[GuitarAuthoringNote | None, UnresolvedGuitarNote | None]:
    if source_note.string_index is None or source_note.fret is None:
        return None, UnresolvedGuitarNote(
            source_start_seconds=source_note.start_seconds,
            midi=source_note.midi,
            reason="string_fret_unresolved",
        )
    if not 0 <= source_note.string_index < 6:
        return None, UnresolvedGuitarNote(
            source_start_seconds=source_note.start_seconds,
            midi=source_note.midi,
            reason="string_out_of_range",
        )
    if source_note.fret < 0 or tuning[source_note.string_index] + source_note.fret != source_note.midi:
        return None, UnresolvedGuitarNote(
            source_start_seconds=source_note.start_seconds,
            midi=source_note.midi,
            reason="string_fret_pitch_mismatch",
        )

    start = map_source_time(alignment, source_note.start_seconds)
    end = map_source_time(alignment, source_note.start_seconds + source_note.duration_seconds)
    duration = max(0.001, end - start)
    review_required = source_note.review_required or source_note.trust_class not in {
        SourceTrustClass.symbolic_verified,
        SourceTrustClass.user_confirmed,
    }
    return GuitarAuthoringNote(
        start_seconds=max(0.0, start),
        duration_seconds=duration,
        midi=source_note.midi,
        string_index=source_note.string_index,
        fret=source_note.fret,
        techniques=list(source_note.techniques),
        trust_class=source_note.trust_class,
        review_required=review_required,
    ), None


def build_guitar_authoring_chart(
    source: ImportedSource,
    alignment: AlignmentReport,
    *,
    arrangement: GuitarArrangement,
    track_index: int | None = None,
    onset_group_tolerance_seconds: float = 0.001,
) -> GuitarAuthoringChart:
    if onset_group_tolerance_seconds <= 0:
        raise ValueError("onset group tolerance must be positive")
    if alignment.source_sha256 != source.provenance.source_sha256:
        raise ValueError("alignment source SHA-256 does not match imported source")

    tracks = [track for track in source.tracks if track.instrument == arrangement]
    if track_index is not None:
        tracks = [track for track in tracks if track.source_track_index == track_index]
    if len(tracks) != 1:
        raise ValueError(f"expected exactly one {arrangement} source track, found {len(tracks)}")
    track = tracks[0]
    if alignment.track_index != track.source_track_index:
        raise ValueError("alignment track index does not match selected guitar source track")
    if track.tuning_midi is None or len(track.tuning_midi) != 6:
        raise ValueError(f"{arrangement} authoring requires an explicit six-string tuning")
    tuning = tuple(int(value) for value in track.tuning_midi)

    positioned: list[GuitarAuthoringNote] = []
    unresolved: list[UnresolvedGuitarNote] = []
    for source_note in track.notes:
        note, problem = _mapped_note(source_note, tuning=tuning, alignment=alignment)
        if note is not None:
            positioned.append(note)
        if problem is not None:
            unresolved.append(problem)

    # Quantize only for grouping. Stored event times remain the mapped floating-point values.
    groups: dict[int, list[GuitarAuthoringNote]] = defaultdict(list)
    for note in positioned:
        bucket = round(note.start_seconds / onset_group_tolerance_seconds)
        groups[bucket].append(note)

    singles: list[GuitarAuthoringNote] = []
    chord_groups: list[list[GuitarAuthoringNote]] = []
    for bucket in sorted(groups):
        notes = sorted(groups[bucket], key=lambda item: (item.string_index, item.fret, item.midi))
        if len(notes) == 1:
            singles.append(notes[0])
            continue
        strings = [note.string_index for note in notes]
        if len(strings) != len(set(strings)):
            unresolved.extend(
                UnresolvedGuitarNote(
                    source_start_seconds=note.start_seconds,
                    midi=note.midi,
                    reason="duplicate_string_in_simultaneous_group",
                )
                for note in notes
            )
            continue
        chord_groups.append(notes)

    shapes = sorted(
        {
            tuple(next((note.fret for note in group if note.string_index == string), -1) for string in range(6))
            for group in chord_groups
        }
    )
    shape_ids = {shape: index for index, shape in enumerate(shapes)}
    chords: list[GuitarChordEvent] = []
    for group in chord_groups:
        shape = tuple(next((note.fret for note in group if note.string_index == string), -1) for string in range(6))
        chords.append(
            GuitarChordEvent(
                start_seconds=min(note.start_seconds for note in group),
                sustain_seconds=max(note.duration_seconds for note in group),
                chord_id=shape_ids[shape],
                shape=shape,
                notes=group,
                review_required=any(note.review_required for note in group),
            )
        )

    warnings: list[str] = []
    if unresolved:
        warnings.append(
            f"{len(unresolved)} guitar note(s) are not exportable until string/fret conflicts are resolved."
        )
    if alignment.confidence < 0.60:
        warnings.append("Alignment confidence is below 0.60; all timing should be reviewed before packaging.")

    return GuitarAuthoringChart(
        arrangement=arrangement,
        source_sha256=source.provenance.source_sha256,
        alignment_confidence=alignment.confidence,
        tuning_midi=tuning,
        single_notes=sorted(singles, key=lambda item: (item.start_seconds, item.string_index)),
        chords=sorted(chords, key=lambda item: (item.start_seconds, item.chord_id)),
        unresolved_notes=sorted(unresolved, key=lambda item: (item.source_start_seconds, item.midi, item.reason)),
        warnings=warnings,
    )


def build_project_guitar_chart(
    project_dir: Path,
    source_path: Path,
    *,
    arrangement: GuitarArrangement,
    alignment_path: Path | None = None,
    track_index: int | None = None,
) -> Path:
    project_dir = project_dir.resolve()
    source_path = source_path.resolve()
    alignment_path = (alignment_path or (project_dir / "analysis" / "alignment.json")).resolve()
    source = ImportedSource.read_json(source_path)
    alignment = AlignmentReport.model_validate_json(alignment_path.read_text(encoding="utf-8"))
    chart = build_guitar_authoring_chart(
        source,
        alignment,
        arrangement=arrangement,
        track_index=track_index,
    )
    return chart.write_json(project_dir / "charts" / f"{arrangement}_source.json")
