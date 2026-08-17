from __future__ import annotations

from contextlib import contextmanager

import pytest

from rocksmith_cdlc_generator.accepted_score_timing import AcceptedScoreTimingMap, AcceptedScoreTimingPoint
from rocksmith_cdlc_generator import reviewed_score_timing_authority as authority_module
from rocksmith_cdlc_generator.reviewed_score_timing_authority import (
    REVIEWED_SCORE_TIMING_PATH,
    ReviewedScoreTimingAuthority,
    load_current_reviewed_score_timing,
    promote_reviewed_score_timing,
)


_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64


def _map(*, middle_time: float = 2.1) -> AcceptedScoreTimingMap:
    points = [
        AcceptedScoreTimingPoint(
            source_beat_index=0,
            source_time_seconds=0.0,
            candidate_time_seconds=1.0,
            reviewed_time_seconds=1.0,
            review_origin="human_anchor",
        ),
        AcceptedScoreTimingPoint(
            source_beat_index=1,
            source_time_seconds=1.0,
            candidate_time_seconds=2.0,
            reviewed_time_seconds=middle_time,
            review_origin="bounded_refit",
        ),
        AcceptedScoreTimingPoint(
            source_beat_index=2,
            source_time_seconds=2.0,
            candidate_time_seconds=3.0,
            reviewed_time_seconds=3.0,
            review_origin="candidate",
        ),
    ]
    return AcceptedScoreTimingMap(
        recording_sha256=_SHA_A,
        score_sha256=_SHA_B,
        authority_track_index=2,
        authority_output_sha256=_SHA_C,
        human_anchor_count=2,
        bounded_region_count=1,
        reviewed_beat_count=2,
        unchanged_beat_count=1,
        max_abs_adjustment_seconds=abs(middle_time - 2.0),
        points=points,
    )


def _locked_transaction(state: dict[str, bool]):
    @contextmanager
    def transaction(_project):
        assert not state["held"]
        state["held"] = True
        try:
            yield
        finally:
            state["held"] = False

    return transaction


def test_promote_reviewed_score_timing_persists_exact_map_under_transaction(tmp_path, monkeypatch) -> None:
    expected = _map()
    state = {"held": False}
    monkeypatch.setattr(authority_module, "score_mapping_transaction", _locked_transaction(state))

    def build_locked(_project):
        assert state["held"]
        return expected

    monkeypatch.setattr(authority_module, "_build_accepted_score_timing_map_locked", build_locked)

    output = promote_reviewed_score_timing(tmp_path, expected_map=expected)

    assert output == tmp_path / REVIEWED_SCORE_TIMING_PATH
    persisted = ReviewedScoreTimingAuthority.read_json(output)
    assert persisted.human_confirmed is True
    assert persisted.method == "accepted-bounded-score-refit-v1"
    assert persisted.timing_map == expected
    assert state["held"] is False


def test_promotion_fails_closed_when_map_changed_after_review(tmp_path, monkeypatch) -> None:
    shown = _map()
    current = _map(middle_time=2.2)
    state = {"held": False}
    monkeypatch.setattr(authority_module, "score_mapping_transaction", _locked_transaction(state))
    monkeypatch.setattr(authority_module, "_build_accepted_score_timing_map_locked", lambda _project: current)

    with pytest.raises(ValueError, match="changed after review"):
        promote_reviewed_score_timing(tmp_path, expected_map=shown)

    assert not (tmp_path / REVIEWED_SCORE_TIMING_PATH).exists()


def test_loader_rejects_promoted_authority_when_current_accepted_map_changed(tmp_path, monkeypatch) -> None:
    persisted_map = _map()
    output = tmp_path / REVIEWED_SCORE_TIMING_PATH
    ReviewedScoreTimingAuthority(timing_map=persisted_map).write_json(output)

    state = {"held": False}
    monkeypatch.setattr(authority_module, "score_mapping_transaction", _locked_transaction(state))

    def build_locked(_project):
        assert state["held"]
        return _map(middle_time=2.2)

    monkeypatch.setattr(authority_module, "_build_accepted_score_timing_map_locked", build_locked)

    with pytest.raises(ValueError, match="authority is stale"):
        load_current_reviewed_score_timing(tmp_path)


def test_loader_returns_current_promoted_authority(tmp_path, monkeypatch) -> None:
    current = _map()
    output = tmp_path / REVIEWED_SCORE_TIMING_PATH
    expected = ReviewedScoreTimingAuthority(timing_map=current)
    expected.write_json(output)

    state = {"held": False}
    monkeypatch.setattr(authority_module, "score_mapping_transaction", _locked_transaction(state))
    monkeypatch.setattr(authority_module, "_build_accepted_score_timing_map_locked", lambda _project: current)

    loaded = load_current_reviewed_score_timing(tmp_path)

    assert loaded == expected


def test_loader_reads_promoted_authority_while_transaction_is_held(tmp_path, monkeypatch) -> None:
    current = _map()
    output = tmp_path / REVIEWED_SCORE_TIMING_PATH
    ReviewedScoreTimingAuthority(timing_map=current).write_json(output)

    state = {"held": False}
    monkeypatch.setattr(authority_module, "score_mapping_transaction", _locked_transaction(state))

    original_read_json = authority_module.ReviewedScoreTimingAuthority.read_json.__func__

    def read_json_locked(cls, path):
        assert state["held"]
        return original_read_json(cls, path)

    def build_locked(_project):
        assert state["held"]
        return current

    monkeypatch.setattr(
        authority_module.ReviewedScoreTimingAuthority,
        "read_json",
        classmethod(read_json_locked),
    )
    monkeypatch.setattr(authority_module, "_build_accepted_score_timing_map_locked", build_locked)

    loaded = load_current_reviewed_score_timing(tmp_path)

    assert loaded.timing_map == current
    assert state["held"] is False
