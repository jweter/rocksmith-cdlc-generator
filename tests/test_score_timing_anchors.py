from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from rocksmith_cdlc_generator.score_timing_anchors import (
    ScoreTimingAnchor,
    ScoreTimingAnchorReview,
    _candidate_time_for_source_beat,
    _load_persisted_review,
    _upsert,
    _validate_recording_time,
    nearest_candidate_anchor,
)


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


def _candidate():
    return SimpleNamespace(
        recording_sha256=_SHA_A,
        score_sha256=_SHA_B,
        authority_track_index=2,
        authority_output_sha256=_SHA_C,
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

    assert review.schema_version == 2
    assert review.anchors[0].source_beat_index == 0
    assert review.anchors[1].source_beat_index == 64
    assert review.anchors[1].origin == "manual_cursor"
    assert review.anchors[1].recording_time_seconds == 33.5


def test_legacy_schema_one_anchor_review_is_rejected_by_current_model() -> None:
    legacy = _review([]).model_dump()
    legacy["schema_version"] = 1

    with pytest.raises(ValueError):
        ScoreTimingAnchorReview.model_validate(legacy)


def test_legacy_schema_one_file_is_discarded_for_safe_rereview(tmp_path) -> None:
    legacy = _review(
        [
            ScoreTimingAnchor(
                source_beat_index=64,
                recording_time_seconds=9999.0,
                origin="manual_cursor",
                candidate_time_seconds=30.0,
            )
        ]
    ).model_dump()
    legacy["schema_version"] = 1
    path = tmp_path / "score_timing_anchors.json"
    path.write_text(json.dumps(legacy), encoding="utf-8")

    review = _load_persisted_review(path, _candidate())

    assert review.schema_version == 2
    assert review.anchors == []


def test_unknown_future_schema_is_not_silently_discarded(tmp_path) -> None:
    future = _review([]).model_dump()
    future["schema_version"] = 99
    path = tmp_path / "score_timing_anchors.json"
    path.write_text(json.dumps(future), encoding="utf-8")

    with pytest.raises(ValueError):
        _load_persisted_review(path, _candidate())


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


def test_upsert_revalidates_recording_time_order() -> None:
    review = _review(
        [
            ScoreTimingAnchor(source_beat_index=8, recording_time_seconds=4.0, origin="manual_cursor"),
            ScoreTimingAnchor(source_beat_index=16, recording_time_seconds=8.0, origin="manual_cursor"),
        ]
    )

    with pytest.raises(ValueError, match="strictly increasing"):
        _upsert(
            review,
            ScoreTimingAnchor(source_beat_index=8, recording_time_seconds=9.0, origin="manual_cursor"),
        )


def test_candidate_time_interpolates_for_selected_score_beat() -> None:
    candidate = SimpleNamespace(
        anchors=[
            SimpleNamespace(source_time_seconds=0.0, audio_time_seconds=1.0),
            SimpleNamespace(source_time_seconds=4.0, audio_time_seconds=5.4),
        ]
    )
    imported = SimpleNamespace(beat_times_seconds=[0.0, 1.0, 2.0, 3.0, 4.0])

    mapped = _candidate_time_for_source_beat(candidate, imported, 2)

    assert mapped == pytest.approx(3.2)


def test_nearest_candidate_anchor_uses_recording_time_and_deterministic_tie_break() -> None:
    candidate = SimpleNamespace(
        anchors=[
            SimpleNamespace(source_beat_index=16, audio_time_seconds=10.0),
            SimpleNamespace(source_beat_index=8, audio_time_seconds=8.0),
        ]
    )

    nearest = nearest_candidate_anchor(candidate, 9.0)

    assert nearest.source_beat_index == 8
    assert nearest.audio_time_seconds == 8.0


def test_nearest_candidate_anchor_returns_none_when_candidate_has_no_anchors() -> None:
    assert nearest_candidate_anchor(SimpleNamespace(anchors=[]), 12.0) is None


def test_recording_time_must_remain_inside_current_audio() -> None:
    assert _validate_recording_time(12.5, 20.0) == 12.5
    with pytest.raises(ValueError, match="inside the current recording duration"):
        _validate_recording_time(20.5, 20.0)
