from __future__ import annotations

from .score_recognition_quality_metrics import RecognitionQualityMetrics


def build_recognition_quality_ui_lines(metrics: RecognitionQualityMetrics) -> tuple[str, ...]:
    """Render deterministic recognition-quality metrics for GUI surfaces.

    This function is intentionally tkinter-free so the review UI can expose the same
    machine-computed quality summary under headless CI without constructing a window.
    It reports recognizer self-confidence/completeness only; it never promotes musical
    correctness or replaces human review authority.
    """

    event_confidence = (
        "n/a" if metrics.mean_event_confidence is None else f"{metrics.mean_event_confidence:.1%}"
    )
    measure_confidence = (
        "n/a"
        if metrics.mean_measure_response_confidence is None
        else f"{metrics.mean_measure_response_confidence:.1%}"
    )

    return (
        f"Clean measures: {metrics.clean_measure_fraction:.1%}",
        (
            "Low-confidence events: "
            f"{metrics.events_below_confidence_threshold}/{metrics.event_count} "
            f"({metrics.low_confidence_event_fraction:.1%})"
        ),
        f"Ambiguous events: {metrics.events_with_ambiguity}",
        f"Measures with deterministic warnings: {metrics.measures_with_deterministic_warnings}",
        f"Geometry review required: {metrics.measures_with_geometry_review_required}",
        f"Mean event confidence: {event_confidence}",
        f"Mean measure confidence: {measure_confidence}",
        f"Candidate-set warnings: {metrics.total_warning_count}",
        "Quality metrics are advisory; human review remains authoritative.",
    )
