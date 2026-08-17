from __future__ import annotations

from types import SimpleNamespace

import pytest

from rocksmith_cdlc_generator import score_timing_anchors
from rocksmith_cdlc_generator.score_timing_anchors import (
    ScoreTimingAnchor,
    ScoreTimingAnchorReview,
    _load_review_for_candidate,
    _require_expected_candidate,
    confirm_candidate_anchor,
    mark_score_beat_at_recording_time,
    save_score_timing_anchor_review,
)


_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64
_SHA_D = "d" * 64


def _candidate(*, recording_sha256: str = _SHA_A, audio_time: float = 10.0):
    return SimpleNamespace(
        recording_sha256=recording_sha256,
        score_sha256=_SHA_B,
        authority_track_index=2,
        authority_output_sha256=_SHA_C,
        anchors=[SimpleNamespace(source_beat_index=8, audio_time_seconds=audio_time)],
    )


def test_current_schema_stale_review_is_discarded_for_fresh_review(tmp_path) -> None:
    stale = ScoreTimingAnchorReview(
        recording_sha256=_SHA_D,
        score_sha256=_SHA_B,
        authority_track_index=2,
        authority_output_sha256=_SHA_C,
        anchors=[
            ScoreTimingAnchor(
                source_beat_index=8,
                recording_time_seconds=9.8,
                origin="manual_cursor",
                candidate_time_seconds=10.0,
            )
        ],
    )
    save_score_timing_anchor_review(tmp_path, stale)

    review = _load_review_for_candidate(tmp_path, _candidate())

    assert review.recording_sha256 == _SHA_A
    assert review.anchors == []


def test_expected_candidate_mismatch_fails_closed() -> None:
    with pytest.raises(ValueError, match="changed after it was shown for review"):
        _require_expected_candidate(_candidate(audio_time=10.2), _candidate(audio_time=10.0))


def test_confirm_candidate_anchor_rejects_candidate_changed_after_dialog(monkeypatch, tmp_path) -> None:
    current = _candidate(audio_time=10.2)
    shown = _candidate(audio_time=10.0)
    monkeypatch.setattr(score_timing_anchors, "build_shared_timeline_candidate", lambda _project: current)

    with pytest.raises(ValueError, match="changed after it was shown for review"):
        confirm_candidate_anchor(tmp_path, 8, expected_candidate=shown)

    assert not (tmp_path / "review" / "score_timing_anchors.json").exists()


def test_manual_anchor_rejects_candidate_changed_after_dialog(monkeypatch, tmp_path) -> None:
    current = _candidate(audio_time=10.2)
    shown = _candidate(audio_time=10.0)
    monkeypatch.setattr(score_timing_anchors, "build_shared_timeline_candidate", lambda _project: current)

    with pytest.raises(ValueError, match="changed after it was shown for review"):
        mark_score_beat_at_recording_time(
            tmp_path,
            8,
            10.0,
            expected_candidate=shown,
        )

    assert not (tmp_path / "review" / "score_timing_anchors.json").exists()
