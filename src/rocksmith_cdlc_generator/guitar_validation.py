from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from .beats import read_tempo_map
from .guitar_authoring import GuitarAuthoringChart
from .models import ProjectManifest
from .rocksmith_xml import unsupported_note_techniques
from .validation import ReviewItem, Status, ValidationReport

GuitarArrangement = Literal["lead", "rhythm"]


def read_guitar_chart(path: Path) -> GuitarAuthoringChart:
    return GuitarAuthoringChart.model_validate_json(path.read_text(encoding="utf-8"))


def _missing(items: list[ReviewItem], path: Path, stage: str) -> None:
    items.append(
        ReviewItem(
            code=f"missing_{stage}",
            severity="FAIL",
            stage=stage,
            message=f"Required artifact is missing: {path}",
            priority=100,
        )
    )


def validate_guitar_project(
    project_dir: Path,
    *,
    arrangement: GuitarArrangement,
) -> ValidationReport:
    project_dir = project_dir.resolve()
    manifest = ProjectManifest.load(project_dir)
    duration = manifest.source_metadata.duration_seconds
    items: list[ReviewItem] = []

    tempo_path = project_dir / "analysis" / "tempo_map.json"
    chart_path = project_dir / "charts" / f"{arrangement}_source.json"

    if not tempo_path.is_file():
        _missing(items, tempo_path, "tempo")
    else:
        tempo_map = read_tempo_map(tempo_path)
        if len(tempo_map.beats) < 2:
            items.append(
                ReviewItem(
                    code="too_few_beats",
                    severity="FAIL",
                    stage="tempo",
                    message="Fewer than two beats were detected.",
                    priority=100,
                )
            )
        for index, beat in enumerate(tempo_map.beats):
            if beat.time > duration + 0.05:
                items.append(
                    ReviewItem(
                        code="beat_out_of_bounds",
                        severity="FAIL",
                        stage="tempo",
                        message=f"Beat {index} occurs after the source audio ends.",
                        time_seconds=beat.time,
                        priority=100,
                    )
                )
            if beat.confidence < 0.30:
                items.append(
                    ReviewItem(
                        code="low_beat_confidence",
                        severity="WARNING",
                        stage="tempo",
                        message=f"Beat {index} has low confidence ({beat.confidence:.2f}).",
                        time_seconds=beat.time,
                        priority=70,
                    )
                )

    if not chart_path.is_file():
        _missing(items, chart_path, f"{arrangement}_chart")
    else:
        try:
            chart = read_guitar_chart(chart_path)
        except Exception as exc:
            items.append(
                ReviewItem(
                    code="invalid_guitar_chart",
                    severity="FAIL",
                    stage="guitar_authoring",
                    message=f"{arrangement.capitalize()} chart cannot be read: {exc}",
                    priority=100,
                )
            )
        else:
            if chart.arrangement != arrangement:
                items.append(
                    ReviewItem(
                        code="guitar_arrangement_mismatch",
                        severity="FAIL",
                        stage="guitar_authoring",
                        message=(
                            f"Expected {arrangement} chart but artifact declares "
                            f"{chart.arrangement}."
                        ),
                        priority=100,
                    )
                )
            if len(chart.tuning_midi) != 6:
                items.append(
                    ReviewItem(
                        code="invalid_guitar_tuning",
                        severity="FAIL",
                        stage="guitar_authoring",
                        message="Guitar tuning must contain exactly six physical-string pitches.",
                        priority=100,
                    )
                )
            if not chart.single_notes and not chart.chords:
                items.append(
                    ReviewItem(
                        code="empty_guitar_chart",
                        severity="FAIL",
                        stage="guitar_authoring",
                        message=f"{arrangement.capitalize()} chart contains no playable events.",
                        priority=100,
                    )
                )

            for unresolved in chart.unresolved_notes:
                items.append(
                    ReviewItem(
                        code="unresolved_guitar_position",
                        severity="FAIL",
                        stage="guitar_authoring",
                        message=(
                            f"MIDI {unresolved.midi} has no exportable string/fret position: "
                            f"{unresolved.reason}."
                        ),
                        time_seconds=unresolved.source_start_seconds,
                        priority=100,
                    )
                )

            def validate_note(note, label: str, index: int) -> None:
                end = note.start_seconds + note.duration_seconds
                if end > duration + 0.05:
                    items.append(
                        ReviewItem(
                            code="guitar_note_out_of_bounds",
                            severity="FAIL",
                            stage="guitar_authoring",
                            message=f"{label} {index} extends beyond the source audio.",
                            time_seconds=note.start_seconds,
                            note_index=index,
                            priority=100,
                        )
                    )
                expected_midi = chart.tuning_midi[note.string_index] + note.fret
                if expected_midi != note.midi:
                    items.append(
                        ReviewItem(
                            code="guitar_position_pitch_mismatch",
                            severity="FAIL",
                            stage="guitar_authoring",
                            message=(
                                f"{label} {index} string/fret reproduces MIDI {expected_midi}, "
                                f"not MIDI {note.midi}."
                            ),
                            time_seconds=note.start_seconds,
                            note_index=index,
                            priority=100,
                        )
                    )
                if note.review_required:
                    items.append(
                        ReviewItem(
                            code="guitar_note_requires_review",
                            severity="WARNING",
                            stage="guitar_authoring",
                            message=f"{label} {index} remains review-required from source trust/alignment.",
                            time_seconds=note.start_seconds,
                            note_index=index,
                            priority=68,
                        )
                    )
                unsupported = unsupported_note_techniques(note)
                if unsupported:
                    items.append(
                        ReviewItem(
                            code="unsupported_imported_technique",
                            severity="WARNING",
                            stage="authoring",
                            message=(
                                f"{label} {index} contains technique(s) not exported losslessly: "
                                f"{', '.join(unsupported)}."
                            ),
                            time_seconds=note.start_seconds,
                            note_index=index,
                            priority=72,
                        )
                    )

            for index, note in enumerate(chart.single_notes):
                validate_note(note, "Single note", index)

            chord_shapes: dict[int, tuple[int, int, int, int, int, int]] = {}
            for chord_index, chord in enumerate(chart.chords):
                previous = chord_shapes.get(chord.chord_id)
                if previous is not None and previous != chord.shape:
                    items.append(
                        ReviewItem(
                            code="chord_id_shape_conflict",
                            severity="FAIL",
                            stage="guitar_authoring",
                            message=(
                                f"Chord id {chord.chord_id} is reused for inconsistent fret shapes."
                            ),
                            time_seconds=chord.start_seconds,
                            priority=100,
                        )
                    )
                chord_shapes[chord.chord_id] = chord.shape
                if chord.start_seconds + chord.sustain_seconds > duration + 0.05:
                    items.append(
                        ReviewItem(
                            code="guitar_chord_out_of_bounds",
                            severity="FAIL",
                            stage="guitar_authoring",
                            message=f"Chord {chord_index} extends beyond the source audio.",
                            time_seconds=chord.start_seconds,
                            priority=100,
                        )
                    )
                if chord.review_required:
                    items.append(
                        ReviewItem(
                            code="guitar_chord_requires_review",
                            severity="WARNING",
                            stage="guitar_authoring",
                            message=f"Chord {chord_index} remains review-required.",
                            time_seconds=chord.start_seconds,
                            priority=70,
                        )
                    )
                for note_index, note in enumerate(chord.notes):
                    validate_note(note, f"Chord {chord_index} note", note_index)

            if chart.alignment_confidence < 0.60:
                items.append(
                    ReviewItem(
                        code="low_guitar_alignment_confidence",
                        severity="WARNING",
                        stage="alignment",
                        message=(
                            f"{arrangement.capitalize()} alignment confidence is "
                            f"{chart.alignment_confidence:.2f}; timing requires review."
                        ),
                        priority=80,
                    )
                )

    items.sort(
        key=lambda item: (
            -item.priority,
            item.time_seconds if item.time_seconds is not None else -1.0,
            item.stage,
            item.code,
        )
    )
    fail_count = sum(item.severity == "FAIL" for item in items)
    warning_count = sum(item.severity == "WARNING" for item in items)
    status: Status = "FAIL" if fail_count else "WARNING" if warning_count else "PASS"
    return ValidationReport(
        status=status,
        can_package=status != "FAIL",
        fail_count=fail_count,
        warning_count=warning_count,
        review_queue=items,
    )


def write_guitar_review_artifacts(
    report: ValidationReport,
    project_dir: Path,
    *,
    arrangement: GuitarArrangement,
) -> dict[str, Path]:
    project_dir = project_dir.resolve()
    review_dir = project_dir / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    validation_path = review_dir / f"{arrangement}_validation_report.json"
    flags_path = review_dir / f"{arrangement}_flags.json"
    summary_path = review_dir / f"{arrangement}_summary.md"

    validation_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    flags_path.write_text(
        json.dumps([item.model_dump(mode="json") for item in report.review_queue], indent=2),
        encoding="utf-8",
    )
    lines = [
        f"# {arrangement.capitalize()} Validation Summary",
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


def validate_guitar_project_to_disk(
    project_dir: Path,
    *,
    arrangement: GuitarArrangement,
) -> Path:
    report = validate_guitar_project(project_dir, arrangement=arrangement)
    return write_guitar_review_artifacts(
        report,
        project_dir,
        arrangement=arrangement,
    )["validation"]
