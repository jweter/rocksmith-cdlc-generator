from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .beats import read_tempo_map
from .fret_mapping import BassMapping, read_bass_mapping
from .models import ProjectManifest
from .reconciliation import SourceDisagreementReport
from .rocksmith_xml import unsupported_note_techniques
from .transcription import BassTranscription, read_transcription

Severity = Literal["INFO", "WARNING", "FAIL"]
Status = Literal["PASS", "WARNING", "FAIL"]


class ReviewItem(BaseModel):
    code: str
    severity: Severity
    stage: str
    message: str
    time_seconds: float | None = Field(default=None, ge=0.0)
    note_index: int | None = Field(default=None, ge=0)
    priority: int = Field(default=50, ge=0, le=100)


class ValidationReport(BaseModel):
    schema_version: int = 1
    status: Status
    can_package: bool
    fail_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    review_queue: list[ReviewItem] = Field(default_factory=list)


def _add_missing(items: list[ReviewItem], path: Path, stage: str) -> None:
    items.append(ReviewItem(code=f"missing_{stage}", severity="FAIL", stage=stage, message=f"Required artifact is missing: {path}", priority=100))


def _validate_timing(items: list[ReviewItem], tempo_path: Path, duration: float) -> None:
    if not tempo_path.is_file():
        _add_missing(items, tempo_path, "tempo")
        return
    tempo_map = read_tempo_map(tempo_path)
    if len(tempo_map.beats) < 2:
        items.append(ReviewItem(code="too_few_beats", severity="FAIL", stage="tempo", message="Fewer than two beats were detected.", priority=100))
        return
    for index, beat in enumerate(tempo_map.beats):
        if beat.time > duration + 0.05:
            items.append(ReviewItem(code="beat_out_of_bounds", severity="FAIL", stage="tempo", message=f"Beat {index} occurs after the source audio ends.", time_seconds=beat.time, priority=100))
        if beat.confidence < 0.30:
            items.append(ReviewItem(code="low_beat_confidence", severity="WARNING", stage="tempo", message=f"Beat {index} has low confidence ({beat.confidence:.2f}).", time_seconds=beat.time, priority=70))


def _validate_transcription(items: list[ReviewItem], transcription: BassTranscription, duration: float) -> None:
    if not transcription.notes:
        items.append(ReviewItem(code="no_bass_notes", severity="FAIL", stage="transcription", message="No bass notes were detected.", priority=100))
        return
    previous_end = 0.0
    for index, note in enumerate(transcription.notes):
        if note.start + note.duration > duration + 0.05:
            items.append(ReviewItem(code="note_out_of_bounds", severity="FAIL", stage="transcription", message=f"Bass note {index} extends beyond the source audio.", time_seconds=note.start, note_index=index, priority=100))
        if index > 0 and note.start < previous_end - 0.01:
            items.append(ReviewItem(code="overlapping_bass_notes", severity="WARNING", stage="transcription", message=f"Bass note {index} overlaps the preceding monophonic note.", time_seconds=note.start, note_index=index, priority=80))
        if note.review_required or note.confidence < 0.55:
            items.append(ReviewItem(code="bass_note_requires_review", severity="WARNING", stage="transcription", message=f"Bass note {index} requires human review (confidence {note.confidence:.2f}).", time_seconds=note.start, note_index=index, priority=85 if note.confidence < 0.40 else 65))
        previous_end = max(previous_end, note.start + note.duration)


def _validate_mapping(items: list[ReviewItem], mapping: BassMapping, duration: float) -> None:
    open_strings = mapping.tuning.open_midi
    if len(open_strings) != 4:
        items.append(ReviewItem(code="invalid_bass_tuning", severity="FAIL", stage="mapping", message="Bass tuning must contain exactly four open-string pitches.", priority=100))
    for index, note in enumerate(mapping.notes):
        if note.start + note.duration > duration + 0.05:
            items.append(ReviewItem(code="mapped_note_out_of_bounds", severity="FAIL", stage="mapping", message=f"Mapped note {index} extends beyond the source audio.", time_seconds=note.start, note_index=index, priority=100))
        if not note.mapped:
            items.append(ReviewItem(code="unmapped_bass_note", severity="FAIL", stage="mapping", message=f"Bass note {index} has no playable string/fret position.", time_seconds=note.start, note_index=index, priority=100))
            continue
        assert note.string is not None and note.fret is not None
        expected_midi = open_strings[note.string] + note.fret
        if expected_midi != note.midi:
            items.append(ReviewItem(code="mapping_pitch_mismatch", severity="FAIL", stage="mapping", message=f"Mapped note {index} string/fret does not reproduce MIDI {note.midi}.", time_seconds=note.start, note_index=index, priority=100))
        if note.fret > mapping.max_fret:
            items.append(ReviewItem(code="fret_limit_exceeded", severity="FAIL", stage="mapping", message=f"Mapped note {index} uses fret {note.fret}, above the configured maximum {mapping.max_fret}.", time_seconds=note.start, note_index=index, priority=100))
        if note.review_required or note.mapping_confidence < 0.65:
            items.append(ReviewItem(code="mapping_requires_review", severity="WARNING", stage="mapping", message=f"Mapped note {index} requires review (mapping confidence {note.mapping_confidence:.2f}).", time_seconds=note.start, note_index=index, priority=60))
        unsupported = unsupported_note_techniques(note)
        if unsupported:
            items.append(ReviewItem(
                code="unsupported_imported_technique",
                severity="WARNING",
                stage="authoring",
                message=f"Mapped note {index} contains imported technique(s) not yet exported losslessly: {', '.join(unsupported)}.",
                time_seconds=note.start,
                note_index=index,
                priority=72,
            ))


def _validate_source_disagreements(items: list[ReviewItem], path: Path) -> None:
    if not path.is_file():
        return
    try:
        report = SourceDisagreementReport.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:
        items.append(ReviewItem(
            code="invalid_source_disagreement_report",
            severity="FAIL",
            stage="reconciliation",
            message=f"Source disagreement report cannot be read: {exc}",
            priority=100,
        ))
        return
    priorities = {"pitch_conflict": 90, "symbolic_only": 78, "audio_only": 76}
    for disagreement in report.disagreements:
        time_seconds = disagreement.audio_start_seconds
        items.append(ReviewItem(
            code=f"source_{disagreement.status}",
            severity="WARNING",
            stage="reconciliation",
            message=disagreement.reason,
            time_seconds=time_seconds,
            priority=priorities[disagreement.status],
        ))


def validate_project(project_dir: Path) -> ValidationReport:
    project_dir = project_dir.resolve()
    manifest = ProjectManifest.load(project_dir)
    duration = manifest.source_metadata.duration_seconds
    items: list[ReviewItem] = []
    tempo_path = project_dir / "analysis" / "tempo_map.json"
    transcription_path = project_dir / "analysis" / "bass_raw.json"
    mapping_path = project_dir / "charts" / "bass_mapped.json"
    disagreements_path = project_dir / "review" / "source_disagreements.json"
    _validate_timing(items, tempo_path, duration)
    if transcription_path.is_file():
        _validate_transcription(items, read_transcription(transcription_path), duration)
    else:
        _add_missing(items, transcription_path, "transcription")
    if mapping_path.is_file():
        _validate_mapping(items, read_bass_mapping(mapping_path), duration)
    else:
        _add_missing(items, mapping_path, "mapping")
    _validate_source_disagreements(items, disagreements_path)
    items.sort(key=lambda item: (-item.priority, item.time_seconds if item.time_seconds is not None else -1.0, item.stage, item.code))
    fail_count = sum(item.severity == "FAIL" for item in items)
    warning_count = sum(item.severity == "WARNING" for item in items)
    status: Status = "FAIL" if fail_count else "WARNING" if warning_count else "PASS"
    return ValidationReport(status=status, can_package=status != "FAIL", fail_count=fail_count, warning_count=warning_count, review_queue=items)


def write_review_artifacts(report: ValidationReport, project_dir: Path) -> dict[str, Path]:
    project_dir = project_dir.resolve()
    review_dir = project_dir / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    validation_path = review_dir / "validation_report.json"
    flags_path = review_dir / "flags.json"
    summary_path = review_dir / "summary.md"
    validation_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    flags_path.write_text(json.dumps([item.model_dump(mode="json") for item in report.review_queue], indent=2), encoding="utf-8")
    lines = [
        "# CDLC Validation Summary",
        "",
        f"**Status:** {report.status}",
        f"**Packaging allowed:** {'yes' if report.can_package else 'no'}",
        f"**Failures:** {report.fail_count}",
        f"**Warnings:** {report.warning_count}",
        "",
        "## Review Queue",
        "",
    ]
    if not report.review_queue:
        lines.append("No unresolved review items.")
    else:
        for item in report.review_queue:
            location = f" @ {item.time_seconds:.3f}s" if item.time_seconds is not None else ""
            lines.append(f"- **{item.severity}** [{item.stage}/{item.code}]{location}: {item.message}")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"validation": validation_path, "flags": flags_path, "summary": summary_path}


def validate_project_to_disk(project_dir: Path) -> Path:
    report = validate_project(project_dir)
    return write_review_artifacts(report, project_dir)["validation"]
