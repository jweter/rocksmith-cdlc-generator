from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.accepted_score_timing import AcceptedScoreTimingPoint
from rocksmith_cdlc_generator.alignment import AlignmentAnchor, AlignmentRegion, AlignmentReport
from rocksmith_cdlc_generator.reviewed_arrangement_timing import ReviewedArrangementTiming
from rocksmith_cdlc_generator.score_preview import (
    _map_preview_source_time,
    _mapped_note,
    _reviewed_timing_if_promoted,
)
from rocksmith_cdlc_generator.score_source import ArrangementRole
from rocksmith_cdlc_generator.source_import import (
    SourceNoteEvent,
    SourceTrustClass,
)


def _candidate_alignment() -> AlignmentReport:
    return AlignmentReport(
        source_path="fixture.json",
        source_sha256="a" * 64,
        recording_sha256="b" * 64,
        track_index=0,
        audio_beat_start_index=0,
        global_offset_seconds=1.0,
        anchor_stride_beats=4,
        matched_beats=3,
        rms_residual_seconds=0.0,
        median_abs_residual_seconds=0.0,
        max_abs_residual_seconds=0.0,
        confidence=1.0,
        anchors=[
            AlignmentAnchor(
                source_time_seconds=0.0,
                audio_time_seconds=1.0,
                source_beat_index=0,
                audio_beat_index=0,
                confidence=1.0,
            ),
            AlignmentAnchor(
                source_time_seconds=2.0,
                audio_time_seconds=3.0,
                source_beat_index=2,
                audio_beat_index=2,
                confidence=1.0,
            ),
        ],
        regions=[
            AlignmentRegion(
                source_start_seconds=0.0,
                source_end_seconds=2.0,
                audio_start_seconds=1.0,
                audio_end_seconds=3.0,
                rms_residual_seconds=0.0,
                max_abs_residual_seconds=0.0,
                confidence=1.0,
            )
        ],
    )


def _reviewed_timing(role: ArrangementRole) -> ReviewedArrangementTiming:
    return ReviewedArrangementTiming(
        role=role,
        source_track_index={
            ArrangementRole.bass: 0,
            ArrangementRole.lead: 1,
            ArrangementRole.rhythm: 2,
        }[role],
        source_output_json=f"sources/imported/{role.value}.json",
        source_output_sha256="c" * 64,
        recording_sha256="b" * 64,
        score_sha256="a" * 64,
        points=[
            AcceptedScoreTimingPoint(
                source_beat_index=0,
                source_time_seconds=0.0,
                candidate_time_seconds=1.0,
                reviewed_time_seconds=2.0,
                review_origin="human_anchor",
            ),
            AcceptedScoreTimingPoint(
                source_beat_index=1,
                source_time_seconds=1.0,
                candidate_time_seconds=2.0,
                reviewed_time_seconds=3.5,
                review_origin="bounded_refit",
            ),
            AcceptedScoreTimingPoint(
                source_beat_index=2,
                source_time_seconds=2.0,
                candidate_time_seconds=3.0,
                reviewed_time_seconds=4.0,
                review_origin="human_anchor",
            ),
        ],
        human_confirmed=True,
    )


def _note() -> SourceNoteEvent:
    return SourceNoteEvent(
        start_seconds=0.5,
        duration_seconds=1.0,
        midi=64,
        note_name="E4",
        string_index=1,
        fret=2,
        import_confidence=0.95,
        trust_class=SourceTrustClass.symbolic_verified,
    )


@pytest.mark.parametrize(
    "role",
    [ArrangementRole.bass, ArrangementRole.lead, ArrangementRole.rhythm],
)
def test_promoted_timing_drives_note_onset_and_end_for_every_arrangement(role: ArrangementRole) -> None:
    alignment = _candidate_alignment()
    timing = _reviewed_timing(role)

    event = _mapped_note(
        alignment,
        _note(),
        event_index=7,
        reviewed_timing=timing,
    )

    # Both endpoints use the same reviewed piecewise transform. This keeps the
    # arrangement aligned to the reviewed beat grid and prevents a candidate-map
    # sustain from leaking across the corrected local timing region.
    assert event.start_seconds == pytest.approx(2.75)
    assert event.duration_seconds == pytest.approx(1.0)
    assert _map_preview_source_time(alignment, timing, 0.5) == pytest.approx(
        event.start_seconds
    )
    assert _map_preview_source_time(alignment, timing, 1.5) == pytest.approx(
        event.start_seconds + event.duration_seconds
    )


def test_explicit_event_timing_override_still_wins_over_song_timing() -> None:
    event = _mapped_note(
        _candidate_alignment(),
        _note(),
        event_index=7,
        reviewed_timing=_reviewed_timing(ArrangementRole.bass),
        timing_override=(8.0, 0.25),
    )

    assert event.start_seconds == pytest.approx(8.0)
    assert event.duration_seconds == pytest.approx(0.25)


def test_promoted_timing_presence_fails_closed_when_authority_is_stale(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    promoted = tmp_path / "analysis" / "reviewed_score_timing.json"
    promoted.parent.mkdir(parents=True)
    promoted.write_text("{}\n", encoding="utf-8")

    def stale(_project: Path, _role: ArrangementRole) -> ReviewedArrangementTiming:
        raise ValueError("reviewed score timing authority is stale")

    monkeypatch.setattr(
        "rocksmith_cdlc_generator.score_preview.reviewed_arrangement_timing",
        stale,
    )

    with pytest.raises(ValueError, match="authority is stale"):
        _reviewed_timing_if_promoted(tmp_path, ArrangementRole.lead)


def test_unpromoted_project_keeps_candidate_preview_compatibility(tmp_path: Path) -> None:
    assert _reviewed_timing_if_promoted(tmp_path, ArrangementRole.rhythm) is None
    assert _map_preview_source_time(
        _candidate_alignment(),
        None,
        0.5,
    ) == pytest.approx(1.5)
