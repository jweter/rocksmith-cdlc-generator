from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.score_timing_anchors import ScoreTimingAnchor, ScoreTimingAnchorReview


_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64


def _review(anchors: list[ScoreTimingAnchor]) -> ScoreTimingAnchorReview:
    return ScoreTimingAnchorReview(
        recording_sha256=_SHA_A,
        score_sha256=_SHA_B,
        authority_track_index=2,
        authority_output_sha256=_SHA_C,
        anchors=anchors,
    )


def test_score_timing_anchor_review_preserves_sparse_score_identity() -> None:
    review = _review(
        [
            ScoreTimingAnchor(
                source_beat_index=0,
                recording_time_seconds=1.25,
                origin="confirmed_candidate",
                candidate_time_seconds=1.25,
            ),
            ScoreTimingAnchor(
                source_beat_index=64,
                recording_time_seconds=33.5,
                origin="manual_cursor",
                candidate_time_seconds=33.42,
            ),
        ]
    )

    assert review.anchors[0].source_beat_index == 0
    assert review.anchors[1].source_beat_index == 64
    assert review.anchors[1].origin == "manual_cursor"
    assert review.anchors[1].recording_time_seconds == 33.5


def test_score_timing_anchor_review_rejects_duplicate_score_beats() -> None:
    with pytest.raises(ValueError, match="unique ascending"):
        _review(
            [
                ScoreTimingAnchor(source_beat_index=8, recording_time_seconds=4.0, origin="manual_cursor"),
                ScoreTimingAnchor(source_beat_index=8, recording_time_seconds=5.0, origin="manual_cursor"),
            ]
        )


def test_score_timing_anchor_review_rejects_reversed_recording_correspondence() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        _review(
            [
                ScoreTimingAnchor(source_beat_index=8, recording_time_seconds=8.0, origin="manual_cursor"),
                ScoreTimingAnchor(source_beat_index=16, recording_time_seconds=7.0, origin="manual_cursor"),
            ]
        )
