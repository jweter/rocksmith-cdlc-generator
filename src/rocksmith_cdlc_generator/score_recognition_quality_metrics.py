from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .score_measure_recognition import PrintedScoreRecognitionCandidateSet


class RecognitionQualityMetrics(BaseModel):
    """Deterministic, self-referential quality signals over one recognition candidate set.

    Every field here is computed only from data the recognizer and its deterministic-warning
    pass already produced (per-event confidence/ambiguity, per-measure geometry/coverage
    warnings). None of it compares against musical ground truth or requires human or model
    judgment: it answers "how much of its own output did the recognizer flag as uncertain,"
    never "was it correct." See docs/printed-notation-tab-practice-mode.md's benchmark-metrics
    note for why ground-truth accuracy stays out of scope here.
    """

    model_config = ConfigDict(frozen=True)

    measure_count: int = Field(ge=0)
    event_count: int = Field(ge=0)
    measures_with_deterministic_warnings: int = Field(ge=0)
    measures_with_geometry_review_required: int = Field(ge=0)
    clean_measure_fraction: float = Field(ge=0.0, le=1.0)
    events_with_ambiguity: int = Field(ge=0)
    events_below_confidence_threshold: int = Field(ge=0)
    low_confidence_event_fraction: float = Field(ge=0.0, le=1.0)
    mean_event_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    mean_measure_response_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    total_warning_count: int = Field(ge=0)


def summarize_candidate_set_quality(
    candidates: PrintedScoreRecognitionCandidateSet,
    *,
    low_confidence_threshold: float = 0.80,
) -> RecognitionQualityMetrics:
    """Aggregate one recognition candidate set into objective completeness/quality counts.

    ``low_confidence_threshold`` mirrors the 0.80 cutoff ``_deterministic_warnings()`` already
    uses to flag ``low_model_confidence`` events, so the fraction reported here stays
    consistent with what the recognizer itself already treats as review-worthy.
    """

    measures = candidates.measures
    measure_count = len(measures)

    events = [event for measure in measures for event in measure.response.events]
    event_count = len(events)

    measures_with_warnings = sum(1 for measure in measures if measure.deterministic_warnings)
    measures_with_geometry_review = sum(1 for measure in measures if measure.geometry_review_required)
    clean_measures = sum(
        1
        for measure in measures
        if not measure.deterministic_warnings and not measure.geometry_review_required
    )

    events_with_ambiguity = sum(1 for event in events if event.ambiguity)
    events_below_threshold = sum(1 for event in events if event.confidence < low_confidence_threshold)

    return RecognitionQualityMetrics(
        measure_count=measure_count,
        event_count=event_count,
        measures_with_deterministic_warnings=measures_with_warnings,
        measures_with_geometry_review_required=measures_with_geometry_review,
        clean_measure_fraction=(clean_measures / measure_count) if measure_count else 1.0,
        events_with_ambiguity=events_with_ambiguity,
        events_below_confidence_threshold=events_below_threshold,
        low_confidence_event_fraction=(events_below_threshold / event_count) if event_count else 0.0,
        mean_event_confidence=(
            sum(event.confidence for event in events) / event_count if event_count else None
        ),
        mean_measure_response_confidence=(
            sum(measure.response.confidence for measure in measures) / measure_count
            if measure_count
            else None
        ),
        total_warning_count=len(candidates.warnings),
    )
