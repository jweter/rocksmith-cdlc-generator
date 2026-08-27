from __future__ import annotations

import hashlib
from pathlib import Path
from statistics import median
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .alignment import AlignmentReport, map_source_time
from .hashing import sha256_file
from .score_source import ArrangementRole
from .shared_timeline import alignment_for_role
from .source_import import ImportedSource, SourceNoteEvent, SourceTrack


EOF_RECORDING_CLOCK_REPORT_PATH = Path("review") / "eof_recording_clock_report.json"
_CONSTANT_OFFSET_SPREAD_SECONDS = 0.15


class EOFRecordingClockObservation(BaseModel):
    """One sparse EOF observation of a source event on the recording clock."""

    model_config = ConfigDict(frozen=True)

    event_index: int = Field(ge=0)
    eof_recording_time_seconds: float = Field(ge=0)
    score_bar: int | None = Field(default=None, ge=1)
    string_index: int | None = Field(default=None, ge=0)
    fret: int | None = Field(default=None, ge=0)
    label: str | None = None

    @model_validator(mode="after")
    def position_is_complete(self) -> "EOFRecordingClockObservation":
        if (self.string_index is None) != (self.fret is None):
            raise ValueError("EOF recording-clock observation position requires both string_index and fret")
        return self


class EOFRecordingClockFixture(BaseModel):
    """Private/source-bound EOF timing evidence for one arrangement role."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    fixture_id: str = Field(min_length=1)
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    recording_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_track_index: int = Field(ge=0)
    instrument: ArrangementRole
    eof_version: str = Field(min_length=1)
    evidence_note: str = Field(min_length=1)
    observations: list[EOFRecordingClockObservation] = Field(min_length=1)

    @model_validator(mode="after")
    def event_indices_are_unique(self) -> "EOFRecordingClockFixture":
        indices = [item.event_index for item in self.observations]
        if len(indices) != len(set(indices)):
            raise ValueError("EOF recording-clock observation event indices must be unique")
        return self


class EOFRecordingClockResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_index: int = Field(ge=0)
    score_bar: int | None = Field(default=None, ge=1)
    label: str | None = None
    source_time_seconds: float = Field(ge=0)
    eof_recording_time_seconds: float = Field(ge=0)
    mapped_recording_time_seconds: float
    delta_seconds: float
    abs_delta_seconds: float = Field(ge=0)
    estimated_bar_delta: float | None = None
    string_index: int | None = Field(default=None, ge=0)
    fret: int | None = Field(default=None, ge=0)


class EOFRecordingClockComparison(BaseModel):
    """Read-only comparison of EOF-observed and generator-mapped recording time."""

    model_config = ConfigDict(frozen=True)

    classification: Literal["insufficient", "constant_offset", "drift"]
    first_playable_delta_seconds: float | None = None
    median_abs_error_seconds: float = Field(ge=0)
    max_abs_error_seconds: float = Field(ge=0)
    delta_spread_seconds: float = Field(ge=0)
    results: list[EOFRecordingClockResult]


class EOFProjectRecordingClockReport(BaseModel):
    """Project-local EOF mapped-timing report; advisory evidence only."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    instrument: ArrangementRole
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    recording_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_track_index: int = Field(ge=0)
    fixture_id: str
    fixture_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    eof_version: str
    evidence_note: str
    shared_timeline_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    timing_tolerance_seconds: float = Field(ge=0)
    comparison: EOFRecordingClockComparison

    @property
    def matched(self) -> bool:
        return self.comparison.max_abs_error_seconds <= self.timing_tolerance_seconds


def _track_for_alignment(source: ImportedSource, alignment: AlignmentReport) -> SourceTrack:
    if source.provenance.source_sha256 != alignment.source_sha256:
        raise ValueError("role source provenance does not match current shared timeline score")
    track = next(
        (item for item in source.tracks if item.source_track_index == alignment.track_index),
        None,
    )
    if track is None:
        raise ValueError("current role source does not contain the shared-timeline source track")
    return track


def _local_bar_seconds(source: ImportedSource, source_time_seconds: float) -> float | None:
    tempo = next(
        (item for item in reversed(source.tempo_events) if item.time_seconds <= source_time_seconds + 1e-9),
        None,
    )
    signature = next(
        (item for item in reversed(source.time_signatures) if item.time_seconds <= source_time_seconds + 1e-9),
        None,
    )
    if tempo is None or signature is None:
        return None
    quarter_notes_per_bar = signature.numerator * (4.0 / signature.denominator)
    return quarter_notes_per_bar * (60.0 / tempo.bpm)


def _validate_observation_identity(
    observation: EOFRecordingClockObservation,
    note: SourceNoteEvent,
) -> None:
    if observation.string_index is None:
        return
    actual = (note.string_index, note.fret)
    expected = (observation.string_index, observation.fret)
    if actual != expected:
        raise ValueError(
            f"EOF observation event {observation.event_index} position {expected} does not match "
            f"the current source event position {actual}; evidence is stale or identifies the wrong event"
        )


def compare_source_to_eof_recording_clock(
    source: ImportedSource,
    alignment: AlignmentReport,
    fixture: EOFRecordingClockFixture,
) -> EOFRecordingClockComparison:
    """Compare sparse EOF observations against the final shared recording-clock transform."""

    if alignment.source_sha256 != fixture.score_sha256:
        raise ValueError("EOF recording-clock fixture is stale for the current score")
    if alignment.recording_sha256 != fixture.recording_sha256:
        raise ValueError("EOF recording-clock fixture is stale for the current recording")
    if alignment.track_index != fixture.source_track_index:
        raise ValueError("EOF recording-clock fixture source track does not match current shared timing")

    track = _track_for_alignment(source, alignment)
    results: list[EOFRecordingClockResult] = []
    for observation in sorted(fixture.observations, key=lambda item: item.event_index):
        if observation.event_index >= len(track.notes):
            raise ValueError(
                f"EOF recording-clock observation event {observation.event_index} is outside the current source track"
            )
        note = track.notes[observation.event_index]
        _validate_observation_identity(observation, note)
        mapped = map_source_time(alignment, note.start_seconds)
        delta = mapped - observation.eof_recording_time_seconds
        bar_seconds = _local_bar_seconds(source, note.start_seconds)
        estimated_bar_delta = None if bar_seconds is None else delta / bar_seconds
        results.append(
            EOFRecordingClockResult(
                event_index=observation.event_index,
                score_bar=observation.score_bar,
                label=observation.label,
                source_time_seconds=note.start_seconds,
                eof_recording_time_seconds=observation.eof_recording_time_seconds,
                mapped_recording_time_seconds=mapped,
                delta_seconds=delta,
                abs_delta_seconds=abs(delta),
                estimated_bar_delta=estimated_bar_delta,
                string_index=note.string_index,
                fret=note.fret,
            )
        )

    deltas = [item.delta_seconds for item in results]
    absolute = [item.abs_delta_seconds for item in results]
    spread = max(deltas) - min(deltas) if len(deltas) > 1 else 0.0
    if len(deltas) < 2:
        classification: Literal["insufficient", "constant_offset", "drift"] = "insufficient"
    elif spread <= _CONSTANT_OFFSET_SPREAD_SECONDS:
        classification = "constant_offset"
    else:
        classification = "drift"

    first_playable = next((item.delta_seconds for item in results if item.event_index == 0), None)
    return EOFRecordingClockComparison(
        classification=classification,
        first_playable_delta_seconds=first_playable,
        median_abs_error_seconds=median(absolute),
        max_abs_error_seconds=max(absolute),
        delta_spread_seconds=spread,
        results=results,
    )


def _project(project_dir: Path) -> Path:
    project = project_dir.expanduser().resolve()
    if not (project / "project.json").is_file():
        raise FileNotFoundError(f"Not a CDLC project: {project}")
    return project


def build_project_eof_recording_clock_report(
    project_dir: Path,
    fixture_path: Path,
    *,
    timing_tolerance_seconds: float = 0.05,
) -> EOFProjectRecordingClockReport:
    """Compare one private EOF timing fixture against the current promoted shared timeline."""

    if timing_tolerance_seconds < 0:
        raise ValueError("timing tolerance must be non-negative")
    project = _project(project_dir)
    fixture_bytes = fixture_path.expanduser().resolve().read_bytes()
    fixture = EOFRecordingClockFixture.model_validate_json(fixture_bytes)
    alignment = alignment_for_role(project, fixture.instrument)
    source = ImportedSource.read_json(Path(alignment.source_path))
    comparison = compare_source_to_eof_recording_clock(source, alignment, fixture)
    timeline_path = project / "analysis" / "shared_timeline.json"
    if not timeline_path.is_file():
        raise FileNotFoundError("current promoted shared timeline not found")
    return EOFProjectRecordingClockReport(
        instrument=fixture.instrument,
        score_sha256=fixture.score_sha256,
        recording_sha256=fixture.recording_sha256,
        source_track_index=fixture.source_track_index,
        fixture_id=fixture.fixture_id,
        fixture_sha256=hashlib.sha256(fixture_bytes).hexdigest(),
        eof_version=fixture.eof_version,
        evidence_note=fixture.evidence_note,
        shared_timeline_sha256=sha256_file(timeline_path),
        timing_tolerance_seconds=timing_tolerance_seconds,
        comparison=comparison,
    )


def write_project_eof_recording_clock_report(
    project_dir: Path,
    fixture_path: Path,
    *,
    timing_tolerance_seconds: float = 0.05,
) -> tuple[Path, EOFProjectRecordingClockReport]:
    project = _project(project_dir)
    report = build_project_eof_recording_clock_report(
        project,
        fixture_path,
        timing_tolerance_seconds=timing_tolerance_seconds,
    )
    destination = project / EOF_RECORDING_CLOCK_REPORT_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    temporary.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return destination, report


def load_current_project_eof_recording_clock_report(
    project_dir: Path,
) -> EOFProjectRecordingClockReport | None:
    """Load the latest report only while it remains bound to current timing authority."""

    project = _project(project_dir)
    destination = project / EOF_RECORDING_CLOCK_REPORT_PATH
    if not destination.is_file():
        return None
    report = EOFProjectRecordingClockReport.model_validate_json(
        destination.read_text(encoding="utf-8")
    )
    alignment = alignment_for_role(project, report.instrument)
    if alignment.source_sha256 != report.score_sha256:
        raise ValueError("EOF recording-clock report is stale for the current score")
    if alignment.recording_sha256 != report.recording_sha256:
        raise ValueError("EOF recording-clock report is stale for the current recording")
    if alignment.track_index != report.source_track_index:
        raise ValueError("EOF recording-clock report is stale for the current source track")
    timeline_path = project / "analysis" / "shared_timeline.json"
    if not timeline_path.is_file() or sha256_file(timeline_path) != report.shared_timeline_sha256:
        raise ValueError("EOF recording-clock report is stale for the current shared timeline")
    return report
