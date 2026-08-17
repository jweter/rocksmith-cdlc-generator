import pytest

from rocksmith_cdlc_generator.accepted_score_timing import AcceptedScoreTimingPoint
from rocksmith_cdlc_generator.reviewed_arrangement_timing import ReviewedArrangementTiming
from rocksmith_cdlc_generator.reviewed_timing_transform import (
    map_reviewed_source_interval,
    map_reviewed_source_time,
)
from rocksmith_cdlc_generator.score_source import ArrangementRole


def _timing() -> ReviewedArrangementTiming:
    points = [
        AcceptedScoreTimingPoint(
            source_beat_index=0,
            source_time_seconds=0.0,
            candidate_time_seconds=1.0,
            reviewed_time_seconds=1.0,
            review_origin="candidate",
        ),
        AcceptedScoreTimingPoint(
            source_beat_index=1,
            source_time_seconds=1.0,
            candidate_time_seconds=2.0,
            reviewed_time_seconds=2.2,
            review_origin="human_anchor",
        ),
        AcceptedScoreTimingPoint(
            source_beat_index=2,
            source_time_seconds=2.0,
            candidate_time_seconds=3.0,
            reviewed_time_seconds=3.0,
            review_origin="human_anchor",
        ),
    ]
    return ReviewedArrangementTiming(
        role=ArrangementRole.lead,
        source_track_index=2,
        source_output_json="sources/imported/lead.json",
        source_output_sha256="a" * 64,
        recording_sha256="b" * 64,
        score_sha256="c" * 64,
        points=points,
        human_confirmed=True,
    )


def test_maps_source_time_piecewise_through_reviewed_beats() -> None:
    timing = _timing()

    assert map_reviewed_source_time(timing, 0.5) == pytest.approx(1.6)
    assert map_reviewed_source_time(timing, 1.5) == pytest.approx(2.6)
    assert map_reviewed_source_time(timing, 1.0) == pytest.approx(2.2)


def test_maps_interval_endpoints_to_preserve_local_tempo_change() -> None:
    start, duration = map_reviewed_source_interval(_timing(), 0.5, 1.0)

    assert start == pytest.approx(1.6)
    assert duration == pytest.approx(1.0)


def test_edge_times_use_nearest_reviewed_segment_without_new_anchors() -> None:
    timing = _timing()

    assert map_reviewed_source_time(timing, 2.5) == pytest.approx(3.4)
    assert map_reviewed_source_time(timing, 0.0) == pytest.approx(1.0)


def test_rejects_invalid_source_interval() -> None:
    timing = _timing()

    with pytest.raises(ValueError, match="duration must be positive"):
        map_reviewed_source_interval(timing, 1.0, 0.0)
    with pytest.raises(ValueError, match="source time must be non-negative"):
        map_reviewed_source_time(timing, -0.01)
