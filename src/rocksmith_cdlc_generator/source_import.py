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


class SourceEventOrigin(BaseModel):
    """Where a recognized event came from within a source page image.

    Additive/optional: only populated by adapters that recognize events from a
    photographed or scanned page (see printed_notation_import.py). Adapters that
    read a native structured file (Guitar Pro, MIDI, MusicXML) leave this unset.
    """

    kind: str
    page: int = Field(ge=1)
    region: tuple[int, int, int, int] | None = None


class SourceTempoEvent(BaseModel):
    tick: int = Field(ge=0)
    time_seconds: float = Field(ge=0)
    bpm: float = Field(gt=0)


class SourceTimeSignatureEvent(BaseModel):
    tick: int = Field(ge=0)
    time_seconds: float = Field(ge=0)
    numerator: int = Field(gt=0)
    denominator: int = Field(gt=0)


class SourceBendPoint(BaseModel):
    """One point on a note's bend curve, already normalized to real-world units.

    ``position`` is the fraction of the note's own duration this point falls at (0.0 at the
    note's start, 1.0 at its end) -- source_import.py has no notion of GP's raw position-tick
    scale, so this is pre-divided rather than carried as a source-specific integer.
    ``semitones`` is the bend's pitch offset in semitones at this point (PyGuitarPro's own GP
    bend-value decoding already rounds to whole-semitone granularity; see
    guitarpro_import.py's _bend_points()).
    """

    position: float = Field(ge=0, le=1)
    semitones: float
    vibrato: bool = False


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
    measure: int | None = Field(default=None, ge=1)
    beat: float | None = Field(default=None, ge=1)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    origin: SourceEventOrigin | None = None
    slide_kinds: list[str] = Field(default_factory=list)
    """Source-specific slide subtype(s) (e.g. "shift", "legato", "into_from_above"), additive
    to and independent of the generic "slide" entry in ``techniques``. See
    guitarpro_import.py's SLIDE_KIND_LABELS for the full set and provenance. Kept separate from
    ``techniques`` because that field is validated against a fixed whitelist elsewhere
    (reviewed_techniques.SUPPORTED_TECHNIQUES, eof_compatibility.py) that a new label would
    silently fail or be filtered out of; this field carries no such contract yet."""
    bend_points: list[SourceBendPoint] = Field(default_factory=list)
    slide_target_fret: int | None = Field(default=None, ge=0)
    """Resolved destination fret for a "shift"/"legato" pitched slide in ``slide_kinds``
    (see guitarpro_import.py's _resolve_slide_target_frets()). Guitar Pro encodes this
    only implicitly as the next note on the same string, so it is left unset when no
    later same-string note exists to resolve it against, or when the only slide
    subtype(s) present are the target-less "into"/"out" variants; both remain
    unsupported for lossless Rocksmith export (see rocksmith_xml.py's
    note_has_exportable_slide_target())."""
    link_next: bool = False
    """True when this note's sustain is meant to continue seamlessly into the next note
    with no fresh pick attack, matching Rocksmith XML's ``linkNext`` attribute. Currently
    only set for a "legato" pitched slide (``slide_kinds`` contains ``"legato"``) once its
    destination fret has been resolved (see guitarpro_import.py's
    _resolve_slide_target_frets()): PyGuitarPro's ``SlideType.legatoSlideTo`` is decoded
    from GP5's slide-type bit 0x02, which raynebc/editor-on-fire's gp_import.c (audited at
    commit c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100) maps 1:1 to
    ``EOF_PRO_GUITAR_NOTE_FLAG_LINKNEXT`` -- a "shift" slide (bit 0x01) never sets it. Left
    unset (False) whenever the slide's destination fret could not be resolved, so a stray
    ``linkNext`` is never emitted without the concrete ``slideTo`` it describes."""

    @model_validator(mode="after")
    def field_confidence_is_normalized(self) -> "SourceNoteEvent":
        if any(not (0.0 <= value <= 1.0) for value in self.field_confidence.values()):
            raise ValueError("field_confidence values must be within [0.0, 1.0]")
        return self

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


class SourceRestEvent(BaseModel):
    """Explicit silent interval preserved from symbolic/recognized source material.

    A rest is musical evidence, not merely the absence of a recognized note. Keeping it
    first-class lets printed-notation recognition distinguish intended silence from a
    missed/low-confidence symbol and gives sustain validation a concrete boundary.
    """

    start_seconds: float = Field(ge=0)
    duration_seconds: float = Field(gt=0)
    import_confidence: float = Field(ge=0, le=1)
    trust_class: SourceTrustClass = SourceTrustClass.symbolic_unverified
    review_required: bool = False
    measure: int | None = Field(default=None, ge=1)
    beat: float | None = Field(default=None, ge=1)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    origin: SourceEventOrigin | None = None

    @model_validator(mode="after")
    def field_confidence_is_normalized(self) -> "SourceRestEvent":
        if any(not (0.0 <= value <= 1.0) for value in self.field_confidence.values()):
            raise ValueError("field_confidence values must be within [0.0, 1.0]")
        return self


class SourceTrack(BaseModel):
    source_track_index: int = Field(ge=0)
    name: str | None = None
    instrument: str
    channel_numbers: list[int] = Field(default_factory=list)
    program_numbers: list[int] = Field(default_factory=list)
    tuning_midi: list[int] | None = None
    notes: list[SourceNoteEvent]
    rests: list[SourceRestEvent] = Field(default_factory=list)

    @model_validator(mode="after")
    def events_are_ordered(self) -> "SourceTrack":
        note_starts = [note.start_seconds for note in self.notes]
        if note_starts != sorted(note_starts):
            raise ValueError("source track notes must be ordered by start time")
        rest_starts = [rest.start_seconds for rest in self.rests]
        if rest_starts != sorted(rest_starts):
            raise ValueError("source track rests must be ordered by start time")
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
