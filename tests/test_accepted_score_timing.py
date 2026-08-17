from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from rocksmith_cdlc_generator import accepted_score_timing
from rocksmith_cdlc_generator.accepted_score_timing import (
    AcceptedScoreTimingMap,
    AcceptedScoreTimingPoint,
    build_accepted_score_timing_map,
)


_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64


def _candidate():
    return SimpleNamespace(
        recording_sha256=_SHA_A,
        score_sha256=_SHA_B,
        authority_track_index=2,
        authority_output_sha256=_SHA_C,
    )


def _refit_point(index: int, candidate: float, refit: float, *, human: bool = False):
    return SimpleNamespace(
        source_beat_index=index,
        candidate_time_seconds=candidate,
        refit_time_seconds=refit,
        human_anchor=human,
    )


def _acceptance():
    return SimpleNamespace(
        candidate=_candidate(),
        preview=SimpleNamespace(
            human_anchor_count=2,
            regions=[
                SimpleNamespace(
                    points=[
                        _refit_point(1, 2.0, 2.1, human=True),
                        _refit_point(2, 3.0, 3.2),
                        _refit_point(3, 4.0, 4.3, human=True),
                    ]
                )
            ],
        ),
    )


def test_materialization_applies_refit_only_inside_accepted_bounds(monkeypatch, tmp_path) -> None:
    acceptance = _acceptance()
    imported = SimpleNamespace(beat_times_seconds=[0.0, 1.0, 2.0, 3.0, 4.0])

    monkeypatch.setattr(accepted_score_timing, "load_current_score_timing_refit_acceptance", lambda project: acceptance)
    monkeypatch.setattr(accepted_score_timing, "_authority_source", lambda project, candidate: imported)
    monkeypatch.setattr(
        accepted_score_timing,
        "_candidate_time_for_source_beat",
        lambda candidate, source, index: float(index + 1),
    )

    result = build_accepted_score_timing_map(tmp_path)

    assert [point.reviewed_time_seconds for point in result.points] == [1.0, 2.1, 3.2, 4.3, 5.0]
    assert [point.review_origin for point in result.points] == [
        "candidate",
        "human_anchor",
        "bounded_refit",
        "human_anchor",
        "candidate",
    ]
    assert result.reviewed_beat_count == 3
    assert result.unchanged_beat_count == 2
    assert result.max_abs_adjustment_seconds == pytest.approx(0.3)


def test_materialization_propagates_stale_acceptance_failure(monkeypatch, tmp_path) -> None:
    def stale(project):
        raise ValueError("bounded timing refit acceptance is stale")

    monkeypatch.setattr(accepted_score_timing, "load_current_score_timing_refit_acceptance", stale)

    with pytest.raises(ValueError, match="acceptance is stale"):
        build_accepted_score_timing_map(tmp_path)


def test_materialization_rejects_conflicting_neighbor_region_endpoint(monkeypatch, tmp_path) -> None:
    acceptance = _acceptance()
    acceptance.preview.regions.append(
        SimpleNamespace(
            points=[
                _refit_point(3, 4.0, 4.4, human=True),
                _refit_point(4, 5.0, 5.0, human=True),
            ]
        )
    )
    imported = SimpleNamespace(beat_times_seconds=[0.0, 1.0, 2.0, 3.0, 4.0])
    monkeypatch.setattr(accepted_score_timing, "load_current_score_timing_refit_acceptance", lambda project: acceptance)
    monkeypatch.setattr(accepted_score_timing, "_authority_source", lambda project, candidate: imported)

    with pytest.raises(ValueError, match="conflicting values"):
        build_accepted_score_timing_map(tmp_path)


def test_accepted_map_rejects_nonmonotonic_reviewed_recording_times() -> None:
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
            reviewed_time_seconds=0.9,
            review_origin="human_anchor",
        ),
    ]

    with pytest.raises(ValidationError, match="reverse or collapse"):
        AcceptedScoreTimingMap(
            recording_sha256=_SHA_A,
            score_sha256=_SHA_B,
            authority_track_index=2,
            authority_output_sha256=_SHA_C,
            human_anchor_count=2,
            bounded_region_count=1,
            reviewed_beat_count=1,
            unchanged_beat_count=1,
            max_abs_adjustment_seconds=1.1,
            points=points,
        )
