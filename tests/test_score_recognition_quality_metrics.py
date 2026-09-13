from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.score_measure_recognition import (
    PrintedScoreRecognitionCandidateSet,
    RecognizedMeasureCandidate,
    VisionCandidateEvent,
    VisionMeasureResponse,
)
from rocksmith_cdlc_generator.score_recognition_quality_metrics import (
    summarize_candidate_set_quality,
)

_HASH = "a" * 64


def _event(*, confidence: float = 0.95, ambiguity: str | None = None, beat: float = 1.0) -> VisionCandidateEvent:
    return VisionCandidateEvent(
        kind="note",
        beat=beat,
        duration_beats=1.0,
        string=0,
        fret=2,
        confidence=confidence,
        ambiguity=ambiguity,
    )


def _measure(
    *,
    measure_index: int,
    events: list[VisionCandidateEvent],
    response_confidence: float = 0.95,
    deterministic_warnings: list[str] | None = None,
    geometry_review_required: bool = False,
) -> RecognizedMeasureCandidate:
    return RecognizedMeasureCandidate(
        measure_index=measure_index,
        system_index=0,
        region=(0, 0, 10, 10),
        geometry_confidence=0.95,
        geometry_review_required=geometry_review_required,
        response=VisionMeasureResponse(events=events, confidence=response_confidence),
        deterministic_warnings=deterministic_warnings or [],
    )


def _candidate_set(
    measures: list[RecognizedMeasureCandidate],
    *,
    warnings: list[str] | None = None,
) -> PrintedScoreRecognitionCandidateSet:
    return PrintedScoreRecognitionCandidateSet(
        model="gemma3:4b",
        bundle_id="bundle-1",
        printed_page=1,
        source_sha256=_HASH,
        derivative_sha256=_HASH,
        derivative_relative_path="page-001.png",
        tuning_midi=[40, 45, 50, 55, 59, 64],
        time_signature_numerator=4,
        time_signature_denominator=4,
        measures=measures,
        warnings=warnings or [],
    )


def test_fully_clean_candidate_set_has_perfect_scores() -> None:
    candidates = _candidate_set(
        [
            _measure(measure_index=0, events=[_event(), _event(beat=2.0)]),
            _measure(measure_index=1, events=[_event(beat=1.0)]),
        ]
    )

    metrics = summarize_candidate_set_quality(candidates)

    assert metrics.measure_count == 2
    assert metrics.event_count == 3
    assert metrics.measures_with_deterministic_warnings == 0
    assert metrics.measures_with_geometry_review_required == 0
    assert metrics.clean_measure_fraction == 1.0
    assert metrics.events_with_ambiguity == 0
    assert metrics.events_below_confidence_threshold == 0
    assert metrics.low_confidence_event_fraction == 0.0
    assert metrics.mean_event_confidence == pytest.approx(0.95)
    assert metrics.mean_measure_response_confidence == pytest.approx(0.95)
    assert metrics.total_warning_count == 0


def test_warnings_ambiguity_and_low_confidence_are_counted() -> None:
    candidates = _candidate_set(
        [
            _measure(
                measure_index=0,
                events=[_event(confidence=0.5), _event(confidence=0.95, ambiguity="unclear fret")],
                deterministic_warnings=["event_0:low_model_confidence=0.500"],
            ),
            _measure(
                measure_index=1,
                events=[_event()],
                geometry_review_required=True,
            ),
        ],
        warnings=["measure_0:event_0:low_model_confidence=0.500", "low_confidence_system_geometry"],
    )

    metrics = summarize_candidate_set_quality(candidates, low_confidence_threshold=0.80)

    assert metrics.measure_count == 2
    assert metrics.event_count == 3
    assert metrics.measures_with_deterministic_warnings == 1
    assert metrics.measures_with_geometry_review_required == 1
    assert metrics.clean_measure_fraction == 0.0
    assert metrics.events_with_ambiguity == 1
    assert metrics.events_below_confidence_threshold == 1
    assert metrics.low_confidence_event_fraction == pytest.approx(1 / 3)
    assert metrics.total_warning_count == 2


def test_custom_confidence_threshold_changes_the_low_confidence_count() -> None:
    candidates = _candidate_set([_measure(measure_index=0, events=[_event(confidence=0.85)])])

    strict = summarize_candidate_set_quality(candidates, low_confidence_threshold=0.90)
    lenient = summarize_candidate_set_quality(candidates, low_confidence_threshold=0.50)

    assert strict.events_below_confidence_threshold == 1
    assert lenient.events_below_confidence_threshold == 0


def test_empty_candidate_set_reports_trivially_clean_with_no_confidence_average() -> None:
    candidates = _candidate_set([])

    metrics = summarize_candidate_set_quality(candidates)

    assert metrics.measure_count == 0
    assert metrics.event_count == 0
    assert metrics.clean_measure_fraction == 1.0
    assert metrics.low_confidence_event_fraction == 0.0
    assert metrics.mean_event_confidence is None
    assert metrics.mean_measure_response_confidence is None
