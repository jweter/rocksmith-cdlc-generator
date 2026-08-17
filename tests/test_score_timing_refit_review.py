from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path

import pytest

from rocksmith_cdlc_generator.alignment import AlignmentAnchor
from rocksmith_cdlc_generator.score_source import ArrangementRole
from rocksmith_cdlc_generator.score_timing_anchors import (
    ScoreTimingRefitPoint,
    ScoreTimingRefitPreview,
    ScoreTimingRefitRegion,
)
from rocksmith_cdlc_generator import score_timing_refit_review
from rocksmith_cdlc_generator.score_timing_refit_review import (
    ScoreTimingRefitAcceptance,
    acceptance_for,
    accept_score_timing_refit,
    require_current_acceptance,
)
from rocksmith_cdlc_generator.shared_timeline import SharedTimeline


_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64


def _candidate(*, recording_sha256: str = _SHA_A) -> SharedTimeline:
    return SharedTimeline(
        recording_sha256=recording_sha256,
        score_sha256=_SHA_B,
        authority_role=ArrangementRole.bass,
        authority_track_index=5,
        authority_output_json="sources/imported/bass.json",
        authority_output_sha256=_SHA_C,
        inherited_roles=[ArrangementRole.bass],
        audio_beat_start_index=0,
        global_offset_seconds=1.0,
        anchor_stride_beats=8,
        matched_beats=2,
        rms_residual_seconds=0.01,
        median_abs_residual_seconds=0.01,
        max_abs_residual_seconds=0.02,
        confidence=0.95,
        anchors=[
            AlignmentAnchor(
                source_time_seconds=0.0,
                audio_time_seconds=1.0,
                source_beat_index=0,
                audio_beat_index=0,
                confidence=0.95,
            ),
            AlignmentAnchor(
                source_time_seconds=4.0,
                audio_time_seconds=5.2,
                source_beat_index=4,
                audio_beat_index=4,
                confidence=0.95,
            ),
        ],
        regions=[],
    )


def _preview(*, middle_time: float = 3.1) -> ScoreTimingRefitPreview:
    points = [
        ScoreTimingRefitPoint(
            source_beat_index=0,
            source_time_seconds=0.0,
            candidate_time_seconds=1.0,
            refit_time_seconds=1.0,
            human_anchor=True,
        ),
        ScoreTimingRefitPoint(
            source_beat_index=2,
            source_time_seconds=2.0,
            candidate_time_seconds=3.1,
            refit_time_seconds=middle_time,
            human_anchor=False,
        ),
        ScoreTimingRefitPoint(
            source_beat_index=4,
            source_time_seconds=4.0,
            candidate_time_seconds=5.2,
            refit_time_seconds=5.2,
            human_anchor=True,
        ),
    ]
    return ScoreTimingRefitPreview(
        recording_sha256=_SHA_A,
        score_sha256=_SHA_B,
        authority_track_index=5,
        authority_output_sha256=_SHA_C,
        human_anchor_count=2,
        max_abs_adjustment_seconds=abs(middle_time - 3.1),
        regions=[
            ScoreTimingRefitRegion(
                start_source_beat_index=0,
                end_source_beat_index=4,
                start_recording_time_seconds=1.0,
                end_recording_time_seconds=5.2,
                max_abs_adjustment_seconds=abs(middle_time - 3.1),
                points=points,
            )
        ],
    )


def test_acceptance_binds_exact_candidate_and_preview() -> None:
    candidate = _candidate()
    preview = _preview(middle_time=3.2)

    acceptance = acceptance_for(candidate, preview)

    assert acceptance.candidate == candidate
    assert acceptance.preview == preview
    assert acceptance.human_confirmed is True
    assert require_current_acceptance(acceptance, candidate, preview) is acceptance


def test_acceptance_rejects_preview_from_other_recording() -> None:
    candidate = _candidate(recording_sha256="d" * 64)

    with pytest.raises(ValueError, match="recording does not match"):
        acceptance_for(candidate, _preview())


def test_current_acceptance_fails_closed_when_refit_changes() -> None:
    candidate = _candidate()
    acceptance = acceptance_for(candidate, _preview(middle_time=3.2))

    with pytest.raises(ValueError, match="acceptance is stale"):
        require_current_acceptance(acceptance, candidate, _preview(middle_time=3.3))


def test_accept_action_revalidates_exact_objects_before_writing(monkeypatch, tmp_path: Path) -> None:
    candidate = _candidate()
    preview = _preview(middle_time=3.2)
    monkeypatch.setattr(score_timing_refit_review, "score_mapping_transaction", lambda _project: nullcontext())
    monkeypatch.setattr(score_timing_refit_review, "build_shared_timeline_candidate", lambda _project: candidate)
    monkeypatch.setattr(
        score_timing_refit_review,
        "build_score_timing_refit_preview",
        lambda _project, *, expected_candidate=None: preview,
    )

    output = accept_score_timing_refit(
        tmp_path,
        expected_candidate=candidate,
        expected_preview=preview,
    )

    persisted = ScoreTimingRefitAcceptance.read_json(output)
    assert persisted == acceptance_for(candidate, preview)
    assert output == tmp_path.resolve() / "review" / "score_timing_refit_acceptance.json"


def test_accept_action_refuses_candidate_changed_after_review(monkeypatch, tmp_path: Path) -> None:
    reviewed = _candidate()
    current = _candidate(recording_sha256="d" * 64)
    monkeypatch.setattr(score_timing_refit_review, "score_mapping_transaction", lambda _project: nullcontext())
    monkeypatch.setattr(score_timing_refit_review, "build_shared_timeline_candidate", lambda _project: current)

    with pytest.raises(ValueError, match="candidate changed after refit review"):
        accept_score_timing_refit(
            tmp_path,
            expected_candidate=reviewed,
            expected_preview=_preview(),
        )

    assert not (tmp_path / "review" / "score_timing_refit_acceptance.json").exists()
