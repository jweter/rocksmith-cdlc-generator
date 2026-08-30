from __future__ import annotations

from array import array
from pathlib import Path
from typing import Literal
import wave

from pydantic import BaseModel, ConfigDict, Field

from .beats import TempoMap
from .click_track_render import count_in_offset_seconds
from .reviewed_export_events import ReviewedExportArrangement, ReviewedExportNote

NAVIGATION_NOTE = (
    "This check evaluates only same-string sustain overlap between this pipeline's own "
    "recognized note events. Unlike guitarpro_import.py's source material (see "
    "eof_rest_boundary_check.py), printed-notation recognition has no first-class explicit-"
    "rest event yet -- a rest is only ever an implicit gap between recognized events (see "
    "docs/printed-notation-tab-practice-mode.md 'Canonical recognized event data'). A note "
    "that overlaps another note on the same string is always a physical chart impossibility "
    "(one string cannot sound two pitches at once) independent of whether a rest was intended "
    "in the gap, so it is checked directly rather than simulated against a rest model that "
    "does not exist here yet."
)

EVIDENCE_NOTE = (
    "Advisory and source-bound only: it may reveal a recognition/authoring defect but never "
    "silently rewrites canonical chart state."
)


class PrintedNotationValidationError(ValueError):
    pass


class SustainOverlapViolation(BaseModel):
    model_config = ConfigDict(frozen=True)

    string_index: int = Field(ge=0)
    first_source_event_index: int = Field(ge=0)
    second_source_event_index: int = Field(ge=0)
    overlap_seconds: float = Field(gt=0)


class PrintedNotationSustainReport(BaseModel):
    """Advisory same-string sustain-overlap check over a printed-notation arrangement.

    Matches the doc's "Critical correctness requirements": sustains must not silently
    bridge into the next event. Never rewrites canonical chart state; see EVIDENCE_NOTE.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    source_output_sha256: str
    note_count: int = Field(ge=0)
    violations: list[SustainOverlapViolation] = Field(default_factory=list)
    boundaries_respected: bool
    reason: str
    navigation_note: str = NAVIGATION_NOTE
    evidence_note: str = EVIDENCE_NOTE

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path


def check_printed_notation_sustain_boundaries(
    arrangement: ReviewedExportArrangement,
    *,
    overlap_tolerance_seconds: float = 1e-6,
) -> PrintedNotationSustainReport:
    """Compare every same-string pair of reviewed notes for a sustain crossing the next onset.

    Pure function: deterministic, no I/O. Notes on different strings are never compared --
    a genuine chord (simultaneous notes on distinct strings) is not a violation.
    """

    if overlap_tolerance_seconds < 0:
        raise PrintedNotationValidationError("overlap tolerance must be non-negative")

    by_string: dict[int, list[ReviewedExportNote]] = {}
    for note in arrangement.notes:
        if note.string_index is None:
            continue
        by_string.setdefault(note.string_index, []).append(note)

    violations: list[SustainOverlapViolation] = []
    for string_index, notes in by_string.items():
        ordered = sorted(notes, key=lambda note: note.reviewed_start_seconds)
        for current, following in zip(ordered, ordered[1:]):
            current_end = current.reviewed_start_seconds + current.reviewed_duration_seconds
            overlap = current_end - following.reviewed_start_seconds
            if overlap > overlap_tolerance_seconds:
                violations.append(
                    SustainOverlapViolation(
                        string_index=string_index,
                        first_source_event_index=current.source_event_index,
                        second_source_event_index=following.source_event_index,
                        overlap_seconds=overlap,
                    )
                )

    boundaries_respected = not violations
    if boundaries_respected:
        reason = (
            f"{len(arrangement.notes)} reviewed note(s) checked; no same-string sustain "
            "overlaps the next event's onset."
        )
    else:
        first = violations[0]
        reason = (
            f"{len(violations)} same-string sustain overlap(s) found: source event "
            f"{first.first_source_event_index} overlaps source event "
            f"{first.second_source_event_index} on string {first.string_index} by "
            f"{first.overlap_seconds:.3f}s."
        )

    return PrintedNotationSustainReport(
        source_output_sha256=arrangement.source_output_sha256,
        note_count=len(arrangement.notes),
        violations=violations,
        boundaries_respected=boundaries_respected,
        reason=reason,
    )


class MeasureClickAlignmentViolation(BaseModel):
    model_config = ConfigDict(frozen=True)

    measure: int = Field(ge=1)
    expected_frame: int = Field(ge=0)
    peak_amplitude: int = Field(ge=0)


class ClickTrackAlignmentReport(BaseModel):
    """Advisory check that every chart measure downbeat has an audible click at the expected
    sample position in a WAV rendered by ``click_track_render.render_click_track_wav``.

    Because the WAV and the tempo map are computed from the same beat-interval arithmetic
    (see click_track_render.py), a violation here almost always means the WAV and tempo map
    it was checked against were not actually a matched pair -- e.g. the wrong
    ``count_in_measures`` was passed to this check, or a stale WAV was checked against an
    edited tempo map -- rather than an in-file synthesis defect.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    measure_count: int = Field(ge=0)
    violations: list[MeasureClickAlignmentViolation] = Field(default_factory=list)
    aligned: bool
    reason: str
    evidence_note: str = EVIDENCE_NOTE

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path


def _read_wav_samples(path: Path) -> tuple[array, int]:
    with wave.open(str(path), "rb") as handle:
        sample_rate = handle.getframerate()
        raw = handle.readframes(handle.getnframes())
    samples = array("h")
    samples.frombytes(raw)
    return samples, sample_rate


def check_click_track_measure_alignment(
    tempo_map: TempoMap,
    click_wav_path: Path,
    *,
    count_in_measures: int,
    amplitude_threshold: int = 500,
    window_seconds: float = 0.025,
) -> ClickTrackAlignmentReport:
    """Verify every measure downbeat lands on an audible click in a rendered click-track WAV.

    This is the acceptance criterion the doc states explicitly under "First proof of
    concept": "click remains sample/clock aligned with measure boundaries from first to
    last measure." Reads the WAV; does not re-render or modify it.
    """

    if not tempo_map.beats:
        raise PrintedNotationValidationError("Tempo map has no beats to check")

    samples, sample_rate = _read_wav_samples(click_wav_path)
    if sample_rate != tempo_map.sample_rate_hz:
        raise PrintedNotationValidationError(
            f"Click WAV sample rate {sample_rate} does not match tempo map sample rate "
            f"{tempo_map.sample_rate_hz}; this is not a matched WAV/tempo-map pair."
        )

    offset_seconds = count_in_offset_seconds(tempo_map, count_in_measures)
    window_frames = max(1, int(round(window_seconds * sample_rate)))

    downbeats = [beat for beat in tempo_map.beats if beat.is_downbeat]
    violations: list[MeasureClickAlignmentViolation] = []
    for beat in downbeats:
        expected_frame = int(round((offset_seconds + beat.time) * sample_rate))
        window = samples[expected_frame : expected_frame + window_frames]
        peak_amplitude = max((abs(sample) for sample in window), default=0)
        if peak_amplitude < amplitude_threshold:
            violations.append(
                MeasureClickAlignmentViolation(
                    measure=beat.measure,
                    expected_frame=expected_frame,
                    peak_amplitude=peak_amplitude,
                )
            )

    aligned = not violations
    if aligned:
        reason = f"All {len(downbeats)} measure downbeat(s) have an audible click at the expected sample."
    else:
        first = violations[0]
        reason = (
            f"{len(violations)} measure(s) missing an audible downbeat click: measure "
            f"{first.measure} expected a click at frame {first.expected_frame} but the loudest "
            f"sample in that window was only {first.peak_amplitude} (threshold {amplitude_threshold})."
        )

    return ClickTrackAlignmentReport(
        measure_count=len(downbeats),
        violations=violations,
        aligned=aligned,
        reason=reason,
    )
