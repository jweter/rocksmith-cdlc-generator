from __future__ import annotations

import json

import pytest

from rocksmith_cdlc_generator.benchmark import (
    BenchmarkChart,
    BenchmarkNote,
    evaluate_chart,
    summarize_suite,
    write_benchmark_report,
)
from rocksmith_cdlc_generator.benchmark_adapters import (
    from_bass_mapping,
    from_bass_transcription,
    from_guitar_authoring,
)
from rocksmith_cdlc_generator.fret_mapping import BassMapping, MappedNote
from rocksmith_cdlc_generator.fretboard import E_STANDARD
from rocksmith_cdlc_generator.guitar_authoring import (
    GuitarAuthoringChart,
    GuitarAuthoringNote,
    UnresolvedGuitarNote,
)
from rocksmith_cdlc_generator.source_import import SourceTrustClass
from rocksmith_cdlc_generator.transcription import BassTranscription, NoteEvent


def _chart(notes, *, edit_seconds=None):
    return BenchmarkChart(
        case_id="fixture",
        arrangement="bass",
        audio_duration_seconds=60.0,
        human_edit_seconds=edit_seconds,
        notes=notes,
    )


def test_perfect_chart_scores_one():
    reference = _chart(
        [
            BenchmarkNote(
                start_seconds=1.0,
                duration_seconds=0.5,
                midi=40,
                string_index=0,
                fret=12,
                techniques=["slide"],
            )
        ]
    )
    predicted = reference.model_copy(deep=True)

    metrics = evaluate_chart(reference, predicted)

    assert metrics.note_precision == 1.0
    assert metrics.note_recall == 1.0
    assert metrics.note_f1 == 1.0
    assert metrics.onset_mae_seconds == 0.0
    assert metrics.duration_mae_seconds == 0.0
    assert metrics.string_fret_accuracy == 1.0
    assert metrics.technique_f1 == 1.0


def test_note_matching_requires_exact_pitch_and_onset_tolerance():
    reference = _chart(
        [
            BenchmarkNote(start_seconds=1.0, duration_seconds=0.5, midi=40),
            BenchmarkNote(start_seconds=2.0, duration_seconds=0.5, midi=42),
        ]
    )
    predicted = _chart(
        [
            BenchmarkNote(start_seconds=1.05, duration_seconds=0.4, midi=40),
            BenchmarkNote(start_seconds=2.01, duration_seconds=0.5, midi=43),
            BenchmarkNote(start_seconds=3.0, duration_seconds=0.5, midi=44),
        ]
    )

    metrics = evaluate_chart(reference, predicted, onset_tolerance_seconds=0.12)

    assert metrics.matched_note_count == 1
    assert metrics.false_positive_count == 2
    assert metrics.false_negative_count == 1
    assert metrics.note_precision == pytest.approx(1 / 3)
    assert metrics.note_recall == pytest.approx(1 / 2)
    assert metrics.onset_mae_seconds == pytest.approx(0.05)
    assert metrics.duration_mae_seconds == pytest.approx(0.1)


def test_position_technique_review_and_edit_metrics_are_independent():
    reference = _chart(
        [
            BenchmarkNote(
                start_seconds=1.0,
                duration_seconds=0.5,
                midi=40,
                string_index=0,
                fret=12,
                techniques=["slide", "vibrato"],
            ),
            BenchmarkNote(
                start_seconds=2.0,
                duration_seconds=0.5,
                midi=45,
                string_index=1,
                fret=12,
            ),
        ]
    )
    predicted = _chart(
        [
            BenchmarkNote(
                start_seconds=1.0,
                duration_seconds=0.5,
                midi=40,
                string_index=1,
                fret=7,
                techniques=["slide", "bend"],
                review_required=True,
            ),
            BenchmarkNote(
                start_seconds=2.0,
                duration_seconds=0.5,
                midi=45,
                unresolved=True,
                review_required=True,
            ),
        ],
        edit_seconds=90.0,
    )

    metrics = evaluate_chart(reference, predicted)

    assert metrics.note_f1 == 1.0
    assert metrics.string_fret_comparable_count == 1
    assert metrics.string_fret_accuracy == 0.0
    assert metrics.technique_true_positive_count == 1
    assert metrics.technique_false_positive_count == 1
    assert metrics.technique_false_negative_count == 1
    assert metrics.technique_precision == pytest.approx(0.5)
    assert metrics.technique_recall == pytest.approx(0.5)
    assert metrics.technique_f1 == pytest.approx(0.5)
    assert metrics.review_burden_ratio == 1.0
    assert metrics.unresolved_ratio == 0.5
    assert metrics.edit_minutes_per_finished_minute == pytest.approx(1.5)


def test_suite_summary_and_report_files(tmp_path):
    first = evaluate_chart(
        _chart([BenchmarkNote(start_seconds=1.0, duration_seconds=0.5, midi=40)]),
        _chart([BenchmarkNote(start_seconds=1.0, duration_seconds=0.5, midi=40)], edit_seconds=60.0),
    )
    second_reference = BenchmarkChart(
        case_id="second",
        arrangement="bass",
        audio_duration_seconds=120.0,
        notes=[BenchmarkNote(start_seconds=1.0, duration_seconds=0.5, midi=42)],
    )
    second_predicted = BenchmarkChart(
        case_id="second",
        arrangement="bass",
        audio_duration_seconds=120.0,
        human_edit_seconds=120.0,
        notes=[],
    )
    second = evaluate_chart(second_reference, second_predicted)

    report = summarize_suite([first, second])
    output = write_benchmark_report(report, tmp_path / "benchmark.json")

    assert report.macro_note_f1 == pytest.approx(0.5)
    assert report.mean_edit_minutes_per_finished_minute == pytest.approx(1.0)
    assert output.is_file()
    assert output.with_suffix(".md").is_file()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert len(payload["cases"]) == 2


def test_bass_transcription_adapter_preserves_review_state():
    transcription = BassTranscription(
        engine="fixture",
        source_path="audio.wav",
        sample_rate_hz=44100,
        notes=[
            NoteEvent(
                start=1.0,
                duration=0.5,
                midi=40,
                confidence=0.8,
                pitch_confidence=0.9,
                timing_confidence=0.7,
                review_required=True,
            )
        ],
    )

    chart = from_bass_transcription(
        transcription,
        case_id="bass-transcription",
        audio_duration_seconds=10.0,
    )

    assert chart.notes[0].midi == 40
    assert chart.notes[0].review_required is True
    assert chart.notes[0].string_index is None


def test_bass_mapping_adapter_marks_unmapped_as_unresolved():
    mapping = BassMapping(
        tuning=E_STANDARD,
        max_fret=24,
        notes=[
            MappedNote(
                start=1.0,
                duration=0.5,
                midi=40,
                source_confidence=0.9,
                mapping_confidence=0.0,
                review_required=True,
            )
        ],
    )

    chart = from_bass_mapping(
        mapping,
        case_id="bass-map",
        audio_duration_seconds=10.0,
    )

    assert chart.notes[0].unresolved is True
    assert chart.notes[0].review_required is True


def test_guitar_adapter_flattens_positioned_and_unresolved_notes():
    chart = GuitarAuthoringChart(
        arrangement="lead",
        source_sha256="a" * 64,
        alignment_confidence=0.9,
        tuning_midi=(40, 45, 50, 55, 59, 64),
        single_notes=[
            GuitarAuthoringNote(
                start_seconds=1.0,
                duration_seconds=0.5,
                midi=45,
                string_index=0,
                fret=5,
                trust_class=SourceTrustClass.user_confirmed,
            )
        ],
        unresolved_notes=[
            UnresolvedGuitarNote(
                source_start_seconds=2.0,
                midi=47,
                reason="fixture",
            )
        ],
    )

    benchmark = from_guitar_authoring(
        chart,
        case_id="lead",
        audio_duration_seconds=10.0,
    )

    assert len(benchmark.notes) == 2
    assert benchmark.notes[0].unresolved is False
    assert benchmark.notes[1].unresolved is True
    assert benchmark.notes[1].review_required is True
