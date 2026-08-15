from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.arrangement_event_selection import (
    locate_arrangement_events,
    select_arrangement_event,
)
from rocksmith_cdlc_generator.song_preview import PreviewArrangement, PreviewNoteEvent, SongPreviewSnapshot
from rocksmith_cdlc_generator.source_import import SourceTrustClass


def _snapshot() -> SongPreviewSnapshot:
    return SongPreviewSnapshot(
        source_filename="score.musicxml",
        source_sha256="a" * 64,
        arrangements=[
            PreviewArrangement(
                instrument="lead",
                part_index=1,
                part_id="P2",
                part_name="Lead Guitar",
                output_json="analysis/score_fanout/lead.json",
                note_count=2,
                tuning_midi=[40, 45, 50, 55, 59, 64],
                notes=[
                    PreviewNoteEvent(
                        event_index=4,
                        start_seconds=1.0,
                        duration_seconds=0.25,
                        midi=64,
                        note_name="E4",
                        string_index=5,
                        fret=0,
                        import_confidence=0.98,
                        trust_class=SourceTrustClass.symbolic_verified,
                        review_required=False,
                    ),
                    PreviewNoteEvent(
                        event_index=5,
                        start_seconds=1.35,
                        duration_seconds=0.10,
                        midi=65,
                        note_name="F4",
                        string_index=5,
                        fret=1,
                        import_confidence=0.72,
                        trust_class=SourceTrustClass.symbolic_unverified,
                        review_required=True,
                    ),
                ],
            ),
            PreviewArrangement(
                instrument="bass",
                part_index=0,
                part_id="P1",
                part_name="Bass",
                output_json="analysis/score_fanout/bass.json",
                note_count=1,
                tuning_midi=[28, 33, 38, 43],
                notes=[
                    PreviewNoteEvent(
                        event_index=2,
                        start_seconds=1.0,
                        duration_seconds=0.5,
                        midi=40,
                        note_name="E2",
                        string_index=0,
                        fret=12,
                        import_confidence=0.91,
                        trust_class=SourceTrustClass.symbolic_verified,
                        review_required=False,
                    )
                ],
            ),
        ],
    )


def _overlapping_snapshot() -> SongPreviewSnapshot:
    snapshot = _snapshot()
    lead = snapshot.arrangements[0]
    lead.notes.append(
        PreviewNoteEvent(
            event_index=6,
            start_seconds=1.0,
            duration_seconds=0.25,
            midi=67,
            note_name="G4",
            string_index=4,
            fret=8,
            import_confidence=0.96,
            trust_class=SourceTrustClass.symbolic_verified,
            review_required=False,
        )
    )
    lead.note_count = 3
    return snapshot


def test_selects_unflagged_event_directly_from_lane() -> None:
    selected = select_arrangement_event(
        _snapshot(), lane_index=0, time_seconds=1.12, tolerance_seconds=0.01
    )

    assert selected is not None
    assert selected.instrument == "lead"
    assert selected.event_index == 4
    assert selected.review_required is False
    assert selected.string_index == 5
    assert selected.fret == 0


def test_selection_is_lane_scoped() -> None:
    selected = select_arrangement_event(
        _snapshot(), lane_index=1, time_seconds=1.12, tolerance_seconds=0.01
    )

    assert selected is not None
    assert selected.instrument == "bass"
    assert selected.event_index == 2


def test_short_event_can_be_hit_with_small_tolerance() -> None:
    selected = select_arrangement_event(
        _snapshot(), lane_index=0, time_seconds=1.47, tolerance_seconds=0.03
    )

    assert selected is not None
    assert selected.event_index == 5


def test_overlapping_events_require_explicit_choice() -> None:
    snapshot = _overlapping_snapshot()
    state = locate_arrangement_events(
        snapshot,
        lane_index=0,
        time_seconds=1.12,
        tolerance_seconds=0.01,
    )

    assert state.requires_choice is True
    assert [candidate.event_index for candidate in state.candidates] == [4, 6]
    assert {candidate.note_name for candidate in state.candidates} == {"E4", "G4"}
    assert (
        select_arrangement_event(
            snapshot,
            lane_index=0,
            time_seconds=1.12,
            tolerance_seconds=0.01,
        )
        is None
    )


def test_empty_lane_location_returns_none() -> None:
    assert (
        select_arrangement_event(
            _snapshot(), lane_index=0, time_seconds=3.0, tolerance_seconds=0.02
        )
        is None
    )


def test_invalid_lane_returns_none_and_negative_tolerance_is_rejected() -> None:
    assert select_arrangement_event(_snapshot(), lane_index=99, time_seconds=1.0) is None
    with pytest.raises(ValueError, match="tolerance_seconds"):
        select_arrangement_event(
            _snapshot(), lane_index=0, time_seconds=1.0, tolerance_seconds=-0.01
        )
