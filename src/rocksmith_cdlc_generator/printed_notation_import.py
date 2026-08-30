from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .deterministic_tempo_map import build_deterministic_tempo_map
from .hashing import sha256_file
from .source_import import (
    ImportedSource,
    SourceEventOrigin,
    SourceNoteEvent,
    SourceProvenance,
    SourceTempoEvent,
    SourceTimeSignatureEvent,
    SourceTrack,
    SourceTrustClass,
)

PRINTED_NOTATION_ADAPTER_ID: Literal["printed-notation-fixture-adapter"] = (
    "printed-notation-fixture-adapter"
)
PRINTED_NOTATION_ADAPTER_VERSION = "1"

ArrangementKind = Literal["bass", "lead", "rhythm"]


class PrintedNotationImportError(ValueError):
    pass


class PrintedNotationTimeSignature(BaseModel):
    numerator: int = Field(default=4, ge=1)
    denominator: int = Field(default=4, ge=1)


class PrintedNotationEvent(BaseModel):
    """One recognized event from a printed notation/TAB page.

    This is the schema a real recognizer (docs/printed-notation-tab-practice-mode.md
    phases N0-N3, not yet implemented) is expected to emit. Until that recognizer
    exists, fixtures matching this schema are hand-authored to stand in for its
    output, so the downstream pipeline (this adapter onward) can be built and
    tested end-to-end ahead of the recognizer itself.
    """

    measure: int = Field(ge=1)
    beat: float = Field(ge=1)
    duration_beats: float = Field(gt=0)
    string: int = Field(ge=0)
    fret: int = Field(ge=0)
    techniques: list[str] = Field(default_factory=list)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    review_required: bool = False
    region: tuple[int, int, int, int] | None = None

    @model_validator(mode="after")
    def field_confidence_is_normalized(self) -> "PrintedNotationEvent":
        if any(not (0.0 <= value <= 1.0) for value in self.field_confidence.values()):
            raise ValueError("field_confidence values must be within [0.0, 1.0]")
        return self


class PrintedNotationPage(BaseModel):
    page_number: int = Field(ge=1)
    events: list[PrintedNotationEvent]

    @model_validator(mode="after")
    def has_events(self) -> "PrintedNotationPage":
        if not self.events:
            raise ValueError("Printed notation page must contain at least one recognized event")
        return self


class PrintedNotationFixture(BaseModel):
    """A hand-authored stand-in for real recognizer output (see module docstring)."""

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
    """Return measure -> (start_seconds, seconds_per_beat), reusing the exact same
    per-measure arithmetic deterministic_tempo_map.py used to build ``tempo_map``, so
    event timing derived here can never drift from the chart's own tempo map."""

    result: dict[int, tuple[float, float]] = {}
    for beat_event in tempo_map.beats:
        if beat_event.is_downbeat:
            seconds_per_beat = 60.0 / beat_event.bpm * (4.0 / denominator)
            result[beat_event.measure] = (beat_event.time, seconds_per_beat)
    return result


def convert_printed_notation_fixture(
    fixture: PrintedNotationFixture,
    *,
    source_path: Path,
    source_sha256: str,
) -> ImportedSource:
    measure_count = max(event.measure for page in fixture.pages for event in page.events)
    time_signature = fixture.time_signature
    tempo_map = build_deterministic_tempo_map(
        measure_count=measure_count,
        bpm=fixture.bpm,
        time_signature_numerator=time_signature.numerator,
        time_signature_denominator=time_signature.denominator,
    )
    measure_starts = _measure_start_times(tempo_map, time_signature.denominator)

    warnings: list[str] = []
    measure_beat_totals: dict[int, float] = {}
    notes: list[SourceNoteEvent] = []

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

            notes.append(
                SourceNoteEvent(
                    start_seconds=start_seconds,
                    duration_seconds=duration_seconds,
                    midi=midi,
                    string_index=event.string,
                    fret=event.fret,
                    techniques=event.techniques,
                    import_confidence=(
                        min(event.field_confidence.values()) if event.field_confidence else 1.0
                    ),
                    trust_class=SourceTrustClass.symbolic_unverified,
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
            measure_beat_totals[event.measure] = (
                measure_beat_totals.get(event.measure, 0.0) + event.duration_beats
            )

    for measure, total_beats in sorted(measure_beat_totals.items()):
        if not math.isclose(total_beats, time_signature.numerator, rel_tol=1e-6, abs_tol=1e-6):
            warnings.append(
                f"Measure {measure} recognized events total {total_beats:g} beats; expected "
                f"{time_signature.numerator:g} beats per measure. Inspect for a missing "
                "rest/dot/tie/tuplet before promoting this measure."
            )

    notes.sort(key=lambda note: (note.start_seconds, note.string_index or 0, note.midi))

    track = SourceTrack(
        source_track_index=0,
        instrument=fixture.instrument,
        tuning_midi=list(fixture.tuning_midi),
        notes=notes,
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
