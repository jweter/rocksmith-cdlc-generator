from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .beats import read_tempo_map
from .fret_mapping import BassMapping, read_bass_mapping
from .human_review_marks import current_marks_for_arrangement
from .models import ProjectManifest
from .reconciliation import SourceDisagreementReport
from .rocksmith_xml import unsupported_note_techniques
from .score_mapping_review import load_score_for_mapping_review
from .timing_review import authoritative_tempo_map_path
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


class ReviewItemGroup(BaseModel):
    severity: Severity
    stage: str
    code: str
    count: int = Field(ge=1)
    first_time_seconds: float | None = Field(default=None, ge=0.0)
    example_message: str
    max_priority: int = Field(ge=0, le=100)


class WarningCategorySummary(BaseModel):
    stage: str
    warning_count: int = Field(ge=1)
    distinct_codes: list[str] = Field(min_length=1)
    max_priority: int = Field(ge=0, le=100)


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


def _validate_human_marks(items: list[ReviewItem], project_dir: Path) -> None:
    """Project explicit user Bass marks into validation without mutating musical data.

    Mirrors ``guitar_validation.py``'s handling of the same human review layer for
    Lead/Rhythm: previously a `wrong` mark on a Bass event updated nothing here, so a
    user could mark a Bass event wrong and it would still pass the packaging gate,
    unlike Lead/Rhythm. ``current_marks_for_arrangement`` also verifies each mark's
    stored (MIDI, onset) against the arrangement's current event at that index before
    it is allowed to gate packaging, so a stale mark can never silently attach to an
    unrelated event.
    """
    try:
        score = load_score_for_mapping_review(project_dir)
    except Exception:
        return
    for mark in current_marks_for_arrangement(project_dir, score.source_sha256, "bass"):
        if mark.state == "wrong":
            items.append(
                ReviewItem(
                    code="human_mark_wrong",
                    severity="FAIL",
                    stage="human_review",
                    message=(
                        f"User marked event {mark.event_index} wrong: string "
                        f"{mark.string_index + 1 if mark.string_index is not None else '?'} fret "
                        f"{mark.fret if mark.fret is not None else '?'} at {mark.source_start_seconds:.3f}s."
                    ),
                    time_seconds=mark.source_start_seconds,
                    note_index=mark.event_index,
                    priority=100,
                )
            )
        else:
            items.append(
                ReviewItem(
                    code="human_mark_questionable",
                    severity="WARNING",
                    stage="human_review",
                    message=(
                        f"User marked event {mark.event_index} questionable: string "
                        f"{mark.string_index + 1 if mark.string_index is not None else '?'} fret "
                        f"{mark.fret if mark.fret is not None else '?'} at {mark.source_start_seconds:.3f}s."
                    ),
                    time_seconds=mark.source_start_seconds,
                    note_index=mark.event_index,
                    priority=95,
                )
            )


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

    if report.omitted_trailing_symbolic_count:
        items.append(ReviewItem(
            code="score_trailing_outside_recording",
            severity="WARNING",
            stage="reconciliation",
            message=(
                f"{report.omitted_trailing_symbolic_count} trailing symbolic score note(s) were preserved in source provenance "
                "but not materialized because their projected onset falls outside the recording."
            ),
            time_seconds=report.first_omitted_projected_time_seconds,
            priority=88,
        ))

    priorities = {"pitch_conflict": 90, "symbolic_only": 78, "audio_only": 76}
    for disagreement in report.disagreements:
        items.append(ReviewItem(
            code=f"source_{disagreement.status}",
            severity="WARNING",
            stage="reconciliation",
            message=disagreement.reason,
            time_seconds=disagreement.audio_start_seconds,
            priority=priorities[disagreement.status],
        ))


def _review_item_sort_key(item: ReviewItem) -> tuple[int, float, str, str]:
    return (
        -item.priority,
        item.time_seconds if item.time_seconds is not None else -1.0,
        item.stage,
        item.code,
    )


def summarize_review_queue(items: list[ReviewItem]) -> list[ReviewItemGroup]:
    grouped: dict[tuple[Severity, str, str], list[ReviewItem]] = {}
    for item in sorted(items, key=_review_item_sort_key):
        grouped.setdefault((item.severity, item.stage, item.code), []).append(item)

    groups = [
        ReviewItemGroup(
            severity=severity,
            stage=stage,
            code=code,
            count=len(members),
            first_time_seconds=next((member.time_seconds for member in members if member.time_seconds is not None), None),
            example_message=members[0].message,
            max_priority=max(member.priority for member in members),
        )
        for (severity, stage, code), members in grouped.items()
    ]
    severity_order: dict[Severity, int] = {"FAIL": 0, "WARNING": 1, "INFO": 2}
    groups.sort(key=lambda group: (-group.max_priority, severity_order[group.severity], group.first_time_seconds if group.first_time_seconds is not None else -1.0, group.stage, group.code))
    return groups


def count_actionable_warnings(items: list[ReviewItem]) -> int:
    """Count distinct WARNING root-cause groups, not raw repeated warning events.

    #375: a real project can carry thousands of repeated WARNING events (e.g. one
    per reconciliation pitch-conflict occurrence) that all collapse to a handful of
    ``(severity, stage, code)`` root causes -- the same grouping ``summarize_review_queue``
    and ``_workspace_review_queue`` already use for the human-facing queue. This is the
    "actionable" count a human actually has to triage. It is presentation-only: it does
    not change ``ValidationReport.warning_count`` (the raw audit-trail total), severity,
    priority, or packaging eligibility, and both counts must keep being shown together
    wherever warnings are displayed so raw evidence volume is never mistaken for
    remaining manual review work.
    """

    return sum(1 for group in summarize_review_queue(items) if group.severity == "WARNING")


def format_actionable_warning_summary(actionable_count: int, raw_count: int) -> str:
    """Render the shared long-form "N actionable warning groups · M underlying warning
    events" phrasing used consistently by Overview, Arrangements, Validation, and Review
    Queue (#375). ``raw_count`` is always the exact machine-readable/audit total; grouping
    never hides or drops it.
    """

    if raw_count == 0:
        return "0 warnings"
    groups_word = "group" if actionable_count == 1 else "groups"
    events_word = "event" if raw_count == 1 else "events"
    return (
        f"{actionable_count} actionable warning {groups_word} · "
        f"{raw_count} underlying warning {events_word}"
    )


def format_actionable_warning_compact(actionable_count: int, raw_count: int) -> str:
    """Compact "actionable/raw" form for narrow table cells; see
    ``format_actionable_warning_summary`` for the full phrasing and rationale.
    """

    if raw_count == 0:
        return "0"
    return f"{actionable_count}/{raw_count}"


def summarize_warning_categories(items: list[ReviewItem]) -> list[WarningCategorySummary]:
    grouped: dict[str, list[ReviewItem]] = {}
    for item in items:
        if item.severity != "WARNING":
            continue
        grouped.setdefault(item.stage, []).append(item)

    summaries = [
        WarningCategorySummary(
            stage=stage,
            warning_count=len(members),
            distinct_codes=sorted({member.code for member in members}),
            max_priority=max(member.priority for member in members),
        )
        for stage, members in grouped.items()
    ]
    summaries.sort(key=lambda summary: (-summary.max_priority, -summary.warning_count, summary.stage))
    return summaries


def _workspace_review_queue(items: list[ReviewItem]) -> list[ReviewItem]:
    """Build a human-sized persisted queue without discarding detailed findings.

    ``flags.json`` remains the complete per-event audit trail. The queue embedded in
    ``validation_report.json`` is what Song Workspace reads, so repeated WARNING/INFO
    findings are collapsed to one representative row per severity/stage/code while
    FAIL findings remain individual and visually/actionably distinct.
    """

    grouped: dict[tuple[Severity, str, str], list[ReviewItem]] = {}
    passthrough: list[ReviewItem] = []
    for item in sorted(items, key=_review_item_sort_key):
        if item.severity == "FAIL":
            passthrough.append(item)
        else:
            grouped.setdefault((item.severity, item.stage, item.code), []).append(item)

    collapsed: list[ReviewItem] = list(passthrough)
    for (severity, stage, code), members in grouped.items():
        first = members[0]
        if len(members) == 1:
            collapsed.append(first)
            continue
        first_time = next((member.time_seconds for member in members if member.time_seconds is not None), None)
        collapsed.append(ReviewItem(
            code=code,
            severity=severity,
            stage=stage,
            message=f"{len(members)} occurrences. Example: {first.message}",
            time_seconds=first_time,
            priority=max(member.priority for member in members),
        ))
    collapsed.sort(key=_review_item_sort_key)
    return collapsed


def validate_project(project_dir: Path) -> ValidationReport:
    project_dir = project_dir.resolve()
    manifest = ProjectManifest.load(project_dir)
    duration = manifest.source_metadata.duration_seconds
    items: list[ReviewItem] = []
    tempo_path = authoritative_tempo_map_path(project_dir)
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
    _validate_human_marks(items, project_dir)
    items.sort(key=_review_item_sort_key)
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

    # Product Reality #365: Song Workspace consumes validation_report.json. Persist a
    # grouped presentation queue there while preserving exact authority counts and the
    # complete detailed event list in flags.json. Grouping is presentation-only: it does
    # not change status/can_package/fail_count/warning_count or suppress audit evidence.
    workspace_report = report.model_copy(update={"review_queue": _workspace_review_queue(report.review_queue)})
    validation_path.write_text(workspace_report.model_dump_json(indent=2), encoding="utf-8")
    flags_path.write_text(json.dumps([item.model_dump(mode="json") for item in report.review_queue], indent=2), encoding="utf-8")

    actionable_warning_count = count_actionable_warnings(report.review_queue)
    lines = [
        "# CDLC Validation Summary",
        "",
        f"**Status:** {report.status}",
        f"**Packaging allowed:** {'yes' if report.can_package else 'no'}",
        f"**Failures:** {report.fail_count}",
        f"**Warnings:** {format_actionable_warning_summary(actionable_warning_count, report.warning_count)}",
        "",
    ]
    warning_categories = summarize_warning_categories(report.review_queue)
    if warning_categories:
        lines.extend([
            "## Warning Categories",
            "",
            "Warning counts are grouped by validation stage for triage; every warning remains in the detailed root-cause summary and machine-readable artifacts.",
            "",
        ])
        for category in warning_categories:
            codes = ", ".join(category.distinct_codes)
            lines.append(f"- **{category.stage} × {category.warning_count}**: {len(category.distinct_codes)} distinct code(s) ({codes})")
        lines.append("")
    lines.extend(["## Review Queue by Root Cause", ""])
    if not report.review_queue:
        lines.append("No unresolved review items.")
    else:
        lines.append("Repeated findings are grouped here for readability; complete per-event findings remain in `validation_report.json` and `flags.json`.")
        lines.append("")
        for group in summarize_review_queue(report.review_queue):
            location = f" first @ {group.first_time_seconds:.3f}s" if group.first_time_seconds is not None else ""
            if group.count == 1:
                lines.append(f"- **{group.severity}** [{group.stage}/{group.code}]{location}: {group.example_message}")
            else:
                lines.append(f"- **{group.severity} × {group.count}** [{group.stage}/{group.code}]{location}: {group.count} occurrences. Example: {group.example_message}")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"validation": validation_path, "flags": flags_path, "summary": summary_path}


def validate_project_to_disk(project_dir: Path) -> Path:
    report = validate_project(project_dir)
    return write_review_artifacts(report, project_dir)["validation"]
