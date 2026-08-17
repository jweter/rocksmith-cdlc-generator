from __future__ import annotations

from types import SimpleNamespace

import pytest

from rocksmith_cdlc_generator.score_timing_anchors import (
    ScoreTimingAnchor,
    ScoreTimingAnchorReview,
    _bounded_refit_regions,
)


_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64


def _candidate():
    return SimpleNamespace(
        anchors=[
            SimpleNamespace(source_time_seconds=0.0, audio_time_seconds=1.0),
            SimpleNamespace(source_time_seconds=4.0, audio_time_seconds=5.0),
            SimpleNamespace(source_time_seconds=8.0, audio_time_seconds=9.0),
        ]
    )


def _imported():
    return SimpleNamespace(beat_times_seconds=[float(index) for index in range(9)])


def _review(anchors: list[ScoreTimingAnchor]) -> ScoreTimingAnchorReview:
    return ScoreTimingAnchorReview(
        recording_sha256=_SHA_A,
        score_sha256=_SHA_B,
        authority_track_index=2,
        authority_output_sha256=_SHA_C,
        anchors=anchors,
    )


def test_bounded_refit_preserves_human_endpoints_and_interpolates_inside() -> None:
    review = _review(
        [
            ScoreTimingAnchor(source_beat_index=2, recording_time_seconds=3.2, origin="manual_cursor", candidate_time_seconds=3.0),
            ScoreTimingAnchor(source_beat_index=6, recording_time_seconds=7.6, origin="manual_cursor", candidate_time_seconds=7.0),
        ]
    )

    regions = _bounded_refit_regions(_candidate(), _imported(), review)

    assert len(regions) == 1
    region = regions[0]
    assert [point.source_beat_index for point in region.points] == [2, 3, 4, 5, 6]
    assert region.points[0].refit_time_seconds == 3.2
    assert region.points[-1].refit_time_seconds == 7.6
    assert region.points[2].refit_time_seconds == pytest.approx(5.4)
    assert region.points[0].human_anchor is True
    assert region.points[2].human_anchor is False
    assert region.points[-1].human_anchor is True
    assert region.max_abs_adjustment_seconds == pytest.approx(0.6)


def test_bounded_refit_never_extrapolates_outside_reviewed_pair() -> None:
    review = _review(
        [
            ScoreTimingAnchor(source_beat_index=3, recording_time_seconds=4.0, origin="confirmed_candidate", candidate_time_seconds=4.0),
            ScoreTimingAnchor(source_beat_index=5, recording_time_seconds=6.25, origin="manual_cursor", candidate_time_seconds=6.0),
        ]
    )

    region = _bounded_refit_regions(_candidate(), _imported(), review)[0]

    assert region.start_source_beat_index == 3
    assert region.end_source_beat_index == 5
    assert {point.source_beat_index for point in region.points} == {3, 4, 5}
    assert all(point.source_beat_index not in {0, 1, 2, 6, 7, 8} for point in region.points)


def test_bounded_refit_builds_one_region_between_each_neighboring_human_anchor() -> None:
    review = _review(
        [
            ScoreTimingAnchor(source_beat_index=1, recording_time_seconds=2.0, origin="confirmed_candidate", candidate_time_seconds=2.0),
            ScoreTimingAnchor(source_beat_index=4, recording_time_seconds=5.2, origin="manual_cursor", candidate_time_seconds=5.0),
            ScoreTimingAnchor(source_beat_index=7, recording_time_seconds=8.4, origin="manual_cursor", candidate_time_seconds=8.0),
        ]
    )

    regions = _bounded_refit_regions(_candidate(), _imported(), review)

    assert [(region.start_source_beat_index, region.end_source_beat_index) for region in regions] == [(1, 4), (4, 7)]
    assert regions[0].points[-1].refit_time_seconds == 5.2
    assert regions[1].points[0].refit_time_seconds == 5.2


def test_bounded_refit_requires_two_human_score_anchors() -> None:
    review = _review(
        [ScoreTimingAnchor(source_beat_index=2, recording_time_seconds=3.0, origin="confirmed_candidate", candidate_time_seconds=3.0)]
    )

    with pytest.raises(ValueError, match="at least two human score anchors"):
        _bounded_refit_regions(_candidate(), _imported(), review)
