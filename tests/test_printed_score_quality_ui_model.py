from rocksmith_cdlc_generator.printed_score_quality_ui_model import (
    build_recognition_quality_ui_lines,
)
from rocksmith_cdlc_generator.score_recognition_quality_metrics import (
    RecognitionQualityMetrics,
)


def test_quality_ui_lines_are_headless_and_preserve_human_authority() -> None:
    metrics = RecognitionQualityMetrics(
        measure_count=4,
        event_count=10,
        measures_with_deterministic_warnings=1,
        measures_with_geometry_review_required=1,
        clean_measure_fraction=0.75,
        events_with_ambiguity=2,
        events_below_confidence_threshold=3,
        low_confidence_event_fraction=0.30,
        mean_event_confidence=0.82,
        mean_measure_response_confidence=0.88,
        total_warning_count=2,
    )

    lines = build_recognition_quality_ui_lines(metrics)

    assert "Clean measures: 75.0%" in lines
    assert "Low-confidence events: 3/10 (30.0%)" in lines
    assert "Ambiguous events: 2" in lines
    assert "Mean event confidence: 82.0%" in lines
    assert "Mean measure confidence: 88.0%" in lines
    assert lines[-1] == "Quality metrics are advisory; human review remains authoritative."


def test_quality_ui_lines_handle_empty_candidate_set_without_fabricated_confidence() -> None:
    metrics = RecognitionQualityMetrics(
        measure_count=0,
        event_count=0,
        measures_with_deterministic_warnings=0,
        measures_with_geometry_review_required=0,
        clean_measure_fraction=1.0,
        events_with_ambiguity=0,
        events_below_confidence_threshold=0,
        low_confidence_event_fraction=0.0,
        mean_event_confidence=None,
        mean_measure_response_confidence=None,
        total_warning_count=0,
    )

    lines = build_recognition_quality_ui_lines(metrics)

    assert "Mean event confidence: n/a" in lines
    assert "Mean measure confidence: n/a" in lines
    assert "Low-confidence events: 0/0 (0.0%)" in lines
