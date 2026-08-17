from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from rocksmith_cdlc_generator.accepted_score_timing import AcceptedScoreTimingMap, AcceptedScoreTimingPoint
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.reviewed_score_timing_authority import ReviewedScoreTimingAuthority
from rocksmith_cdlc_generator.score_source import ArrangementRole
from rocksmith_cdlc_generator import reviewed_arrangement_timing as projection_module
from rocksmith_cdlc_generator.reviewed_arrangement_timing import reviewed_arrangement_timing


_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64


def _timing_map() -> AcceptedScoreTimingMap:
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
            reviewed_time_seconds=2.1,
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
        max_abs_adjustment_seconds=0.1,
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


@pytest.mark.parametrize(
    ("role", "track_index"),
    [
        (ArrangementRole.bass, 2),
        (ArrangementRole.lead, 5),
        (ArrangementRole.rhythm, 7),
    ],
)
def test_reviewed_timing_projects_same_song_authority_to_each_confirmed_role(
    tmp_path, monkeypatch, role, track_index
) -> None:
    timing_map = _timing_map()
    authority = ReviewedScoreTimingAuthority(timing_map=timing_map)
    state = {"held": False}
    monkeypatch.setattr(projection_module, "score_mapping_transaction", _locked_transaction(state))

    mapping = SimpleNamespace(role=role, source_track_index=track_index, human_confirmed=True)
    score = SimpleNamespace(source_sha256=_SHA_B, mapping_for=lambda requested: mapping if requested is role else None)
    output_rel = f"sources/imported/{role.value}.json"
    output = tmp_path / output_rel
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(role.value, encoding="utf-8")
    entry = SimpleNamespace(role=role, source_track_index=track_index, output_json=output_rel)

    def load_authority_locked(_project):
        assert state["held"]
        return authority

    def load_score(_project):
        assert state["held"]
        return score

    def current_fanout(_project, current_score):
        assert state["held"]
        assert current_score is score
        return SimpleNamespace(arrangements=[entry])

    monkeypatch.setattr(projection_module, "_load_current_reviewed_score_timing_locked", load_authority_locked)
    monkeypatch.setattr(projection_module, "load_score_for_mapping_review", load_score)
    monkeypatch.setattr(projection_module, "_current_fanout", current_fanout)

    projected = reviewed_arrangement_timing(tmp_path, role)

    assert projected.role is role
    assert projected.source_track_index == track_index
    assert projected.source_output_json == output_rel
    assert projected.source_output_sha256 == sha256_file(output)
    assert projected.recording_sha256 == timing_map.recording_sha256
    assert projected.score_sha256 == timing_map.score_sha256
    assert projected.points == timing_map.points
    assert projected.human_confirmed is True
    assert state["held"] is False


def test_reviewed_timing_rejects_unconfirmed_role(tmp_path, monkeypatch) -> None:
    timing_map = _timing_map()
    authority = ReviewedScoreTimingAuthority(timing_map=timing_map)
    state = {"held": False}
    monkeypatch.setattr(projection_module, "score_mapping_transaction", _locked_transaction(state))
    monkeypatch.setattr(
        projection_module,
        "_load_current_reviewed_score_timing_locked",
        lambda _project: authority,
    )
    score = SimpleNamespace(
        source_sha256=_SHA_B,
        mapping_for=lambda _role: SimpleNamespace(source_track_index=5, human_confirmed=False),
    )
    monkeypatch.setattr(projection_module, "load_score_for_mapping_review", lambda _project: score)

    with pytest.raises(ValueError, match="lead score mapping is not human-confirmed"):
        reviewed_arrangement_timing(tmp_path, ArrangementRole.lead)

    assert state["held"] is False


def test_reviewed_timing_rejects_stale_role_fanout(tmp_path, monkeypatch) -> None:
    timing_map = _timing_map()
    authority = ReviewedScoreTimingAuthority(timing_map=timing_map)
    state = {"held": False}
    monkeypatch.setattr(projection_module, "score_mapping_transaction", _locked_transaction(state))
    monkeypatch.setattr(
        projection_module,
        "_load_current_reviewed_score_timing_locked",
        lambda _project: authority,
    )
    mapping = SimpleNamespace(source_track_index=5, human_confirmed=True)
    score = SimpleNamespace(source_sha256=_SHA_B, mapping_for=lambda _role: mapping)
    monkeypatch.setattr(projection_module, "load_score_for_mapping_review", lambda _project: score)
    monkeypatch.setattr(
        projection_module,
        "_current_fanout",
        lambda _project, _score: SimpleNamespace(
            arrangements=[SimpleNamespace(role=ArrangementRole.lead, source_track_index=6, output_json="stale.json")]
        ),
    )

    with pytest.raises(ValueError, match="lead fan-out output is not current"):
        reviewed_arrangement_timing(tmp_path, ArrangementRole.lead)

    assert state["held"] is False
