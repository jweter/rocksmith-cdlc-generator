from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator import shared_timeline
from rocksmith_cdlc_generator.alignment import AlignmentAnchor, AlignmentRegion
from rocksmith_cdlc_generator.score_source import ArrangementRole
from rocksmith_cdlc_generator.shared_timeline import SharedTimeline


def _candidate(*, second_audio_time: float) -> SharedTimeline:
    return SharedTimeline(
        recording_sha256="1" * 64,
        score_sha256="2" * 64,
        authority_role=ArrangementRole.bass,
        authority_track_index=1,
        authority_output_json="sources/imported/score-bass.json",
        authority_output_sha256="3" * 64,
        inherited_roles=[ArrangementRole.bass, ArrangementRole.lead, ArrangementRole.rhythm],
        audio_beat_start_index=4,
        global_offset_seconds=2.0,
        anchor_stride_beats=8,
        matched_beats=4,
        rms_residual_seconds=0.01,
        median_abs_residual_seconds=0.01,
        max_abs_residual_seconds=0.02,
        confidence=0.94,
        anchors=[
            AlignmentAnchor(
                source_time_seconds=0.0,
                audio_time_seconds=2.0,
                source_beat_index=0,
                audio_beat_index=4,
                confidence=0.95,
            ),
            AlignmentAnchor(
                source_time_seconds=1.5,
                audio_time_seconds=second_audio_time,
                source_beat_index=3,
                audio_beat_index=7,
                confidence=0.93,
            ),
        ],
        regions=[
            AlignmentRegion(
                source_start_seconds=0.0,
                source_end_seconds=1.5,
                audio_start_seconds=2.0,
                audio_end_seconds=second_audio_time,
                rms_residual_seconds=0.01,
                max_abs_residual_seconds=0.02,
                confidence=0.94,
            )
        ],
        human_confirmed=True,
    )


def test_promotion_rejects_candidate_changed_after_human_review(monkeypatch, tmp_path: Path) -> None:
    reviewed = _candidate(second_audio_time=3.5)
    regenerated = _candidate(second_audio_time=3.6)
    monkeypatch.setattr(shared_timeline, "build_shared_timeline_candidate", lambda _project: regenerated)

    with pytest.raises(ValueError, match="changed after review"):
        shared_timeline._promote_shared_timeline_locked(tmp_path, expected_candidate=reviewed)

    assert not (tmp_path / "analysis" / "shared_timeline.json").exists()


def test_promotion_writes_exact_candidate_when_review_identity_still_matches(monkeypatch, tmp_path: Path) -> None:
    reviewed = _candidate(second_audio_time=3.5)
    monkeypatch.setattr(shared_timeline, "build_shared_timeline_candidate", lambda _project: reviewed)

    output = shared_timeline._promote_shared_timeline_locked(tmp_path, expected_candidate=reviewed)

    assert SharedTimeline.read_json(output) == reviewed
