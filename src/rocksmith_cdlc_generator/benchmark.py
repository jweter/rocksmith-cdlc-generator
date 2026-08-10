from __future__ import annotations

from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, Field


class BenchmarkNote(BaseModel):
    start_seconds: float = Field(ge=0.0)
    duration_seconds: float = Field(gt=0.0)
    midi: int = Field(ge=0, le=127)
    string_index: int | None = Field(default=None, ge=0)
    fret: int | None = Field(default=None, ge=0)
    techniques: list[str] = Field(default_factory=list)
    review_required: bool = False
    unresolved: bool = False


class BenchmarkChart(BaseModel):
    schema_version: int = 1
    case_id: str
    arrangement: str
    audio_duration_seconds: float = Field(gt=0.0)
    notes: list[BenchmarkNote]
    human_edit_seconds: float | None = Field(default=None, ge=0.0)


class BenchmarkMetrics(BaseModel):
    schema_version: int = 1
    case_id: str
    arrangement: str
    reference_note_count: int
    predicted_note_count: int
    matched_note_count: int
    false_positive_count: int
    false_negative_count: int
    note_precision: float = Field(ge=0.0, le=1.0)
    note_recall: float = Field(ge=0.0, le=1.0)
    note_f1: float = Field(ge=0.0, le=1.0)
    onset_mae_seconds: float | None = Field(default=None, ge=0.0)
    duration_mae_seconds: float | None = Field(default=None, ge=0.0)
    string_fret_comparable_count: int = Field(ge=0)
    string_fret_match_count: int = Field(ge=0)
    string_fret_accuracy: float | None = Field(default=None, ge=0.0, le=1.0)
    technique_true_positive_count: int = Field(ge=0)
    technique_false_positive_count: int = Field(ge=0)
    technique_false_negative_count: int = Field(ge=0)
    technique_precision: float | None = Field(default=None, ge=0.0, le=1.0)
    technique_recall: float | None = Field(default=None, ge=0.0, le=1.0)
    technique_f1: float | None = Field(default=None, ge=0.0, le=1.0)
    review_required_count: int = Field(ge=0)
    review_burden_ratio: float = Field(ge=0.0, le=1.0)
    unresolved_count: int = Field(ge=0)
    unresolved_ratio: float = Field(ge=0.0, le=1.0)
    human_edit_seconds: float | None = Field(default=None, ge=0.0)
    edit_minutes_per_finished_minute: float | None = Field(default=None, ge=0.0)


class BenchmarkSuiteReport(BaseModel):
    schema_version: int = 1
    cases: list[BenchmarkMetrics]
    macro_note_f1: float = Field(ge=0.0, le=1.0)
    macro_string_fret_accuracy: float | None = Field(default=None, ge=0.0, le=1.0)
    macro_technique_f1: float | None = Field(default=None, ge=0.0, le=1.0)
    mean_onset_mae_seconds: float | None = Field(default=None, ge=0.0)
    mean_edit_minutes_per_finished_minute: float | None = Field(default=None, ge=0.0)


def _safe_ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _f1(precision: float, recall: float) -> float:
    return 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0


def _mean(values: Iterable[float]) -> float | None:
    rows = list(values)
    return sum(rows) / len(rows) if rows else None


def _match_notes(
    reference: list[BenchmarkNote],
    predicted: list[BenchmarkNote],
    *,
    onset_tolerance_seconds: float,
) -> list[tuple[int, int]]:
    """Greedy one-to-one match by exact MIDI, then smallest onset error.

    This deliberately separates note identity from fretboard position. A predicted
    note is musically matched only when pitch agrees and onset is within tolerance;
    physical string/fret correctness is scored independently on those matched notes.
    """
    candidates: list[tuple[float, int, int]] = []
    for ref_index, ref_note in enumerate(reference):
        for pred_index, pred_note in enumerate(predicted):
            if ref_note.midi != pred_note.midi:
                continue
            onset_error = abs(ref_note.start_seconds - pred_note.start_seconds)
            if onset_error <= onset_tolerance_seconds:
                candidates.append((onset_error, ref_index, pred_index))
    candidates.sort()

    used_reference: set[int] = set()
    used_predicted: set[int] = set()
    matches: list[tuple[int, int]] = []
    for _, ref_index, pred_index in candidates:
        if ref_index in used_reference or pred_index in used_predicted:
            continue
        used_reference.add(ref_index)
        used_predicted.add(pred_index)
        matches.append((ref_index, pred_index))
    matches.sort(key=lambda pair: pair[0])
    return matches


def evaluate_chart(
    reference: BenchmarkChart,
    predicted: BenchmarkChart,
    *,
    onset_tolerance_seconds: float = 0.12,
) -> BenchmarkMetrics:
    if reference.case_id != predicted.case_id:
        raise ValueError("Benchmark case_id mismatch")
    if reference.arrangement != predicted.arrangement:
        raise ValueError("Benchmark arrangement mismatch")
    if onset_tolerance_seconds <= 0:
        raise ValueError("onset_tolerance_seconds must be positive")

    matches = _match_notes(
        reference.notes,
        predicted.notes,
        onset_tolerance_seconds=onset_tolerance_seconds,
    )
    matched = len(matches)
    false_positives = len(predicted.notes) - matched
    false_negatives = len(reference.notes) - matched
    precision = _safe_ratio(matched, len(predicted.notes))
    recall = _safe_ratio(matched, len(reference.notes))

    onset_errors = [
        abs(reference.notes[ref_i].start_seconds - predicted.notes[pred_i].start_seconds)
        for ref_i, pred_i in matches
    ]
    duration_errors = [
        abs(reference.notes[ref_i].duration_seconds - predicted.notes[pred_i].duration_seconds)
        for ref_i, pred_i in matches
    ]

    position_pairs = [
        (reference.notes[ref_i], predicted.notes[pred_i])
        for ref_i, pred_i in matches
        if reference.notes[ref_i].string_index is not None
        and reference.notes[ref_i].fret is not None
        and predicted.notes[pred_i].string_index is not None
        and predicted.notes[pred_i].fret is not None
    ]
    position_matches = sum(
        ref.string_index == pred.string_index and ref.fret == pred.fret
        for ref, pred in position_pairs
    )

    technique_tp = 0
    technique_fp = 0
    technique_fn = 0
    for ref_i, pred_i in matches:
        expected = set(reference.notes[ref_i].techniques)
        actual = set(predicted.notes[pred_i].techniques)
        technique_tp += len(expected & actual)
        technique_fp += len(actual - expected)
        technique_fn += len(expected - actual)
    technique_precision = (
        technique_tp / (technique_tp + technique_fp)
        if technique_tp + technique_fp
        else None
    )
    technique_recall = (
        technique_tp / (technique_tp + technique_fn)
        if technique_tp + technique_fn
        else None
    )
    technique_f1 = (
        _f1(technique_precision, technique_recall)
        if technique_precision is not None and technique_recall is not None
        else None
    )

    review_count = sum(note.review_required for note in predicted.notes)
    unresolved_count = sum(note.unresolved for note in predicted.notes)
    predicted_count = len(predicted.notes)
    edit_seconds = predicted.human_edit_seconds
    edit_rate = (
        edit_seconds / predicted.audio_duration_seconds
        if edit_seconds is not None
        else None
    )

    return BenchmarkMetrics(
        case_id=reference.case_id,
        arrangement=reference.arrangement,
        reference_note_count=len(reference.notes),
        predicted_note_count=predicted_count,
        matched_note_count=matched,
        false_positive_count=false_positives,
        false_negative_count=false_negatives,
        note_precision=precision,
        note_recall=recall,
        note_f1=_f1(precision, recall),
        onset_mae_seconds=_mean(onset_errors),
        duration_mae_seconds=_mean(duration_errors),
        string_fret_comparable_count=len(position_pairs),
        string_fret_match_count=position_matches,
        string_fret_accuracy=(
            position_matches / len(position_pairs) if position_pairs else None
        ),
        technique_true_positive_count=technique_tp,
        technique_false_positive_count=technique_fp,
        technique_false_negative_count=technique_fn,
        technique_precision=technique_precision,
        technique_recall=technique_recall,
        technique_f1=technique_f1,
        review_required_count=review_count,
        review_burden_ratio=_safe_ratio(review_count, predicted_count),
        unresolved_count=unresolved_count,
        unresolved_ratio=_safe_ratio(unresolved_count, predicted_count),
        human_edit_seconds=edit_seconds,
        edit_minutes_per_finished_minute=edit_rate,
    )


def summarize_suite(cases: list[BenchmarkMetrics]) -> BenchmarkSuiteReport:
    if not cases:
        raise ValueError("Benchmark suite requires at least one case")
    return BenchmarkSuiteReport(
        cases=cases,
        macro_note_f1=sum(case.note_f1 for case in cases) / len(cases),
        macro_string_fret_accuracy=_mean(
            case.string_fret_accuracy
            for case in cases
            if case.string_fret_accuracy is not None
        ),
        macro_technique_f1=_mean(
            case.technique_f1 for case in cases if case.technique_f1 is not None
        ),
        mean_onset_mae_seconds=_mean(
            case.onset_mae_seconds
            for case in cases
            if case.onset_mae_seconds is not None
        ),
        mean_edit_minutes_per_finished_minute=_mean(
            case.edit_minutes_per_finished_minute
            for case in cases
            if case.edit_minutes_per_finished_minute is not None
        ),
    )


def write_benchmark_chart(chart: BenchmarkChart, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(chart.model_dump_json(indent=2), encoding="utf-8")
    return destination


def read_benchmark_chart(path: Path) -> BenchmarkChart:
    return BenchmarkChart.model_validate_json(path.read_text(encoding="utf-8"))


def write_benchmark_report(report: BenchmarkSuiteReport, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path = destination.with_suffix(".md")
    lines = [
        "# Benchmark Report",
        "",
        f"- Cases: {len(report.cases)}",
        f"- Macro note F1: {report.macro_note_f1:.3f}",
        f"- Macro string/fret accuracy: {report.macro_string_fret_accuracy:.3f}" if report.macro_string_fret_accuracy is not None else "- Macro string/fret accuracy: n/a",
        f"- Macro technique F1: {report.macro_technique_f1:.3f}" if report.macro_technique_f1 is not None else "- Macro technique F1: n/a",
        f"- Mean onset MAE: {report.mean_onset_mae_seconds:.3f}s" if report.mean_onset_mae_seconds is not None else "- Mean onset MAE: n/a",
        f"- Mean edit min / finished min: {report.mean_edit_minutes_per_finished_minute:.3f}" if report.mean_edit_minutes_per_finished_minute is not None else "- Mean edit min / finished min: n/a",
        "",
        "## Cases",
        "",
    ]
    for case in report.cases:
        lines.extend(
            [
                f"### {case.case_id} — {case.arrangement}",
                "",
                f"- Note precision / recall / F1: {case.note_precision:.3f} / {case.note_recall:.3f} / {case.note_f1:.3f}",
                f"- Onset MAE: {case.onset_mae_seconds:.3f}s" if case.onset_mae_seconds is not None else "- Onset MAE: n/a",
                f"- Duration MAE: {case.duration_mae_seconds:.3f}s" if case.duration_mae_seconds is not None else "- Duration MAE: n/a",
                f"- String/fret accuracy: {case.string_fret_accuracy:.3f}" if case.string_fret_accuracy is not None else "- String/fret accuracy: n/a",
                f"- Technique F1: {case.technique_f1:.3f}" if case.technique_f1 is not None else "- Technique F1: n/a",
                f"- Review burden: {case.review_required_count}/{case.predicted_note_count} ({case.review_burden_ratio:.1%})",
                f"- Unresolved: {case.unresolved_count}/{case.predicted_note_count} ({case.unresolved_ratio:.1%})",
                f"- Human edit time: {case.human_edit_seconds:.1f}s" if case.human_edit_seconds is not None else "- Human edit time: not recorded",
                f"- Edit min / finished min: {case.edit_minutes_per_finished_minute:.3f}" if case.edit_minutes_per_finished_minute is not None else "- Edit min / finished min: not recorded",
                "",
            ]
        )
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return destination
