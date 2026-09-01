from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .beats import TempoMap
from .deterministic_tempo_map import build_deterministic_tempo_map
from .hashing import sha256_file
from .source_import import (
    ImportedSource,
    SourceEventOrigin,
    SourceNoteEvent,
    SourceProvenance,
    SourceRestEvent,
    SourceTempoEvent,
    SourceTimeSignatureEvent,
    SourceTrack,
    SourceTrustClass,
)

PRINTED_NOTATION_ADAPTER_ID: Literal["printed-notation-fixture-adapter"] = (
    "printed-notation-fixture-adapter"
)
PRINTED_NOTATION_ADAPTER_VERSION = "2"

ArrangementKind = Literal["bass", "lead", "rhythm"]


class PrintedNotationImportError(ValueError):
    pass


class PrintedNotationTimeSignature(BaseModel):
    numerator: int = Field(default=4, ge=1)
    denominator: int = Field(default=4, ge=1)


class PrintedNotationEvent(BaseModel):
    """One recognized sounded event from a printed notation/TAB page."""

    measure: int = Field(ge=1)
    beat: float = Field(ge=1)
    duration_beats: float = Field(gt=0)
    string: int = Field(ge=0)
    fret: int = Field(ge=0)
    techniques: list[str] = Field(default_factory=list)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    review_required: bool = False
    region: tuple[int, int, int, int] | None = None
    human_reviewed: bool = False
    """Set once a person has explicitly confirmed this recognized event (the doc's
    "review-approved corrections become review authority"). Until then the event
    stays at ``SourceTrustClass.symbolic_unverified`` and downstream authoring
    refuses to promote it, by design."""

    @model_validator(mode="after")
    def field_confidence_is_normalized(self) -> "PrintedNotationEvent":
        if any(not (0.0 <= value <= 1.0) for value in self.field_confidence.values()):
            raise ValueError("field_confidence values must be within [0.0, 1.0]")
        return self


class PrintedNotationRestEvent(BaseModel):
    """One explicitly recognized silent interval from printed notation.

    This is intentionally separate from ``PrintedNotationEvent``: a rest has timing,
    provenance, confidence, and review state but no string/fret pitch. Treating rests as
    first-class evidence prevents recognition failures from being confused with intended
    silence and provides a hard boundary for later sustain validation.
    """

    measure: int = Field(ge=1)
    beat: float = Field(ge=1)
    duration_beats: float = Field(gt=0)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    review_required: bool = False
    region: tuple[int, int, int, int] | None = None
    human_reviewed: bool = False

    @model_validator(mode="after")
    def field_confidence_is_normalized(self) -> "PrintedNotationRestEvent":
        if any(not (0.0 <= value <= 1.0) for value in self.field_confidence.values()):
            raise ValueError("field_confidence values must be within [0.0, 1.0]")
        return self


class PrintedNotationPage(BaseModel):
    page_number: int = Field(ge=1)
    events: list[PrintedNotationEvent] = Field(default_factory=list)
    rests: list[PrintedNotationRestEvent] = Field(default_factory=list)

    @model_validator(mode="after")
    def has_events_or_rests(self) -> "PrintedNotationPage":
        if not self.events and not self.rests:
            raise ValueError(
                "Printed notation page must contain at least one recognized note or rest"
            )
        return self


class PrintedNotationFixture(BaseModel):
    """A recognized-event fixture consumed by the deterministic authoring pipeline."""

    schema_version: int = 1
    instrument: ArrangementKind
    tuning_midi: list[int]
    bpm: float = Field(gt=0)
    time_signature: PrintedNotationTimeSignature = Field(
        default_factory=PrintedNotationTimeSignature
    )
    pages: list[PrintedNotationPage]

    @model_validator(mode="after")
    def has_pages(self) -> "PrintedNotationFixture":
        if not self.pages:
            raise ValueError("Printed notation fixture must contain at least one page")
        return self

    @classmethod
    def read_json(cls, path: Path) -> "PrintedNotationFixture":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


def printed_notation_adapter_sha256() -> str:
    """Fingerprint the complete adapter implementation for derivative evidence."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _measure_start_times(tempo_map, denominator: int) -> dict[int, tuple[float, float]]:
    """Return measure -> (start_seconds, seconds_per_beat), matching tempo-map arithmetic."""

    result: dict[int, tuple[float, float]] = {}
    for beat_event in tempo_map.beats:
        if beat_event.is_downbeat:
            seconds_per_beat = 60.0 / beat_event.bpm * (4.0 / denominator)
            result[beat_event.measure] = (beat_event.time, seconds_per_beat)
    return result


def _fixture_measure_count(fixture: PrintedNotationFixture) -> int:
    measures = [event.measure for page in fixture.pages for event in page.events]
    measures.extend(rest.measure for page in fixture.pages for rest in page.rests)
    if not measures:
        raise PrintedNotationImportError("Printed notation fixture contains no timed events")
    return max(measures)


def printed_notation_tempo_map(fixture: PrintedNotationFixture) -> TempoMap:
    """Build the one authoritative tempo map for a fixture's full recognized range."""

    return build_deterministic_tempo_map(
        measure_count=_fixture_measure_count(fixture),
        bpm=fixture.bpm,
        time_signature_numerator=fixture.time_signature.numerator,
        time_signature_denominator=fixture.time_signature.denominator,
    )


def _confidence(values: dict[str, float]) -> float:
    return min(values.values()) if values else 1.0


def _trust_class(human_reviewed: bool) -> SourceTrustClass:
    return (
        SourceTrustClass.user_confirmed
        if human_reviewed
        else SourceTrustClass.symbolic_unverified
    )


def _measure_interval_coverage(
    intervals: list[tuple[float, float]],
) -> tuple[float, list[tuple[float, float]]]:
    """Return union coverage in beat units, preserving chords/overlapping notes correctly."""

    if not intervals:
        return 0.0, []
    ordered = sorted(intervals)
    merged: list[list[float]] = []
    for start, end in ordered:
        if not merged or start > merged[-1][1] + 1e-9:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    normalized = [(start, end) for start, end in merged]
    return sum(end - start for start, end in normalized), normalized


def convert_printed_notation_fixture(
    fixture: PrintedNotationFixture,
    *,
    source_path: Path,
    source_sha256: str,
) -> ImportedSource:
    time_signature = fixture.time_signature
    tempo_map = printed_notation_tempo_map(fixture)
    measure_starts = _measure_start_times(tempo_map, time_signature.denominator)

    warnings: list[str] = []
    measure_intervals: dict[int, list[tuple[float, float]]] = {}
    note_intervals: dict[int, list[tuple[float, float]]] = {}
    rest_intervals: dict[int, list[tuple[float, float]]] = {}
    notes: list[SourceNoteEvent] = []
    rests: list[SourceRestEvent] = []

    for page in fixture.pages:
        for event in page.events:
            if event.string >= len(fixture.tuning_midi):
                raise PrintedNotationImportError(
                    f"Page {page.page_number} measure {event.measure} references string "
                    f"{event.string} outside the declared {len(fixture.tuning_midi)}-string tuning"
                )
            start_measure_time, seconds_per_beat = measure_starts[event.measure]
            start_seconds = start_measure_time + (event.beat - 1) * seconds_per_beat
            duration_seconds = event.duration_beats * seconds_per_beat
            midi = fixture.tuning_midi[event.string] + event.fret
            beat_start = event.beat - 1.0
            beat_end = beat_start + event.duration_beats

            notes.append(
                SourceNoteEvent(
                    start_seconds=start_seconds,
                    duration_seconds=duration_seconds,
                    midi=midi,
                    string_index=event.string,
                    fret=event.fret,
                    techniques=event.techniques,
                    import_confidence=_confidence(event.field_confidence),
                    trust_class=_trust_class(event.human_reviewed),
                    review_required=event.review_required,
                    measure=event.measure,
                    beat=event.beat,
                    field_confidence=event.field_confidence,
                    origin=SourceEventOrigin(
                        kind="printed_tab_image",
                        page=page.page_number,
                        region=event.region,
                    ),
                )
            )
            measure_intervals.setdefault(event.measure, []).append((beat_start, beat_end))
            note_intervals.setdefault(event.measure, []).append((beat_start, beat_end))

        for rest in page.rests:
            start_measure_time, seconds_per_beat = measure_starts[rest.measure]
            start_seconds = start_measure_time + (rest.beat - 1) * seconds_per_beat
            duration_seconds = rest.duration_beats * seconds_per_beat
            beat_start = rest.beat - 1.0
            beat_end = beat_start + rest.duration_beats

            rests.append(
                SourceRestEvent(
                    start_seconds=start_seconds,
                    duration_seconds=duration_seconds,
                    import_confidence=_confidence(rest.field_confidence),
                    trust_class=_trust_class(rest.human_reviewed),
                    review_required=rest.review_required,
                    measure=rest.measure,
                    beat=rest.beat,
                    field_confidence=rest.field_confidence,
                    origin=SourceEventOrigin(
                        kind="printed_notation_image",
                        page=page.page_number,
                        region=rest.region,
                    ),
                )
            )
            measure_intervals.setdefault(rest.measure, []).append((beat_start, beat_end))
            rest_intervals.setdefault(rest.measure, []).append((beat_start, beat_end))

    for measure, intervals in sorted(measure_intervals.items()):
        coverage, _merged = _measure_interval_coverage(intervals)
        if not math.isclose(
            coverage,
            time_signature.numerator,
            rel_tol=1e-6,
            abs_tol=1e-6,
        ):
            warnings.append(
                f"Measure {measure} recognized note/rest coverage is {coverage:g} beats; expected "
                f"{time_signature.numerator:g} beats per measure. Inspect for a missing "
                "rest/dot/tie/tuplet before promoting this measure."
            )

        for note_start, note_end in note_intervals.get(measure, []):
            for rest_start, rest_end in rest_intervals.get(measure, []):
                overlap = min(note_end, rest_end) - max(note_start, rest_start)
                if overlap > 1e-6:
                    warnings.append(
                        f"Measure {measure} has a recognized note interval overlapping an explicit "
                        f"rest by {overlap:g} beat(s); review the source before promotion."
                    )
                    break

    notes.sort(key=lambda note: (note.start_seconds, note.string_index or 0, note.midi))
    rests.sort(key=lambda rest: rest.start_seconds)

    track = SourceTrack(
        source_track_index=0,
        instrument=fixture.instrument,
        tuning_midi=list(fixture.tuning_midi),
        notes=notes,
        rests=rests,
    )
    return ImportedSource(
        provenance=SourceProvenance(
            source_type="printed_notation_fixture",
            source_filename=source_path.name,
            source_sha256=source_sha256,
            importer=PRINTED_NOTATION_ADAPTER_ID,
            importer_version=PRINTED_NOTATION_ADAPTER_VERSION,
        ),
        tempo_events=[SourceTempoEvent(tick=0, time_seconds=0.0, bpm=fixture.bpm)],
        time_signatures=[
            SourceTimeSignatureEvent(
                tick=0,
                time_seconds=0.0,
                numerator=time_signature.numerator,
                denominator=time_signature.denominator,
            )
        ],
        tracks=[track],
        warnings=warnings,
    )


def import_printed_notation(path: Path) -> ImportedSource:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() != ".json":
        raise PrintedNotationImportError(
            "Printed notation importer expects a .json recognized-event fixture"
        )
    try:
        fixture = PrintedNotationFixture.read_json(path)
    except PrintedNotationImportError:
        raise
    except Exception as exc:
        raise PrintedNotationImportError(
            f"Failed to parse printed notation fixture: {path.name}"
        ) from exc
    return convert_printed_notation_fixture(
        fixture, source_path=path, source_sha256=sha256_file(path)
    )


def import_project_printed_notation(project_dir: Path, fixture_path: Path) -> Path:
    project_dir = project_dir.resolve()
    if not (project_dir / "project.json").is_file():
        raise FileNotFoundError(f"Project manifest not found: {project_dir / 'project.json'}")
    imported = import_printed_notation(fixture_path)
    stem = Path(imported.provenance.source_filename).stem
    instrument = imported.tracks[0].instrument
    destination = (
        project_dir
        / "sources"
        / "imported"
        / f"{stem}-{instrument}-{imported.provenance.source_sha256[:12]}.json"
    )
    return imported.write_json(destination)
