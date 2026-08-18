from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.score_role_composition import (
    ScoreRoleCompositionPlan,
    ScoreRoleCompositionSelection,
)
from rocksmith_cdlc_generator.score_role_composition_overlap import (
    analyze_score_role_composition_overlaps,
)
from rocksmith_cdlc_generator.score_source import ArrangementRole
from rocksmith_cdlc_generator.source_import import SourceNoteEvent, SourceTrack


def _note(
    start: float,
    duration: float,
    midi: int,
    *,
    string_index: int | None = 0,
    fret: int | None = 0,
) -> SourceNoteEvent:
    return SourceNoteEvent(
        start_seconds=start,
        duration_seconds=duration,
        midi=midi,
        string_index=string_index,
        fret=fret,
        import_confidence=1.0,
    )


def _track(index: int, notes: list[SourceNoteEvent]) -> SourceTrack:
    return SourceTrack(
        source_track_index=index,
        name=f"Track {index}",
        instrument="guitar",
        notes=notes,
    )


def _plan(*indexes: int) -> ScoreRoleCompositionPlan:
    return ScoreRoleCompositionPlan(
        score_sha256="a" * 64,
        score_format="gp5",
        selections=[
            ScoreRoleCompositionSelection(
                role=ArrangementRole.lead,
                source_track_indices=list(indexes),
            )
        ],
    )


def test_non_overlapping_selected_tracks_have_no_review_pressure() -> None:
    report = analyze_score_role_composition_overlaps(
        _plan(1, 2),
        [
            _track(1, [_note(0.0, 0.5, 60)]),
            _track(2, [_note(1.0, 0.5, 64)]),
        ],
    )

    summary = report.roles[0]
    assert summary.role is ArrangementRole.lead
    assert summary.source_track_indices == [1, 2]
    assert summary.overlap_count == 0
    assert summary.overlaps == []


def test_exact_duplicate_is_reported_with_both_source_event_identities() -> None:
    report = analyze_score_role_composition_overlaps(
        _plan(1, 2),
        [
            _track(1, [_note(1.0, 0.5, 64, string_index=1, fret=2)]),
            _track(2, [_note(1.0, 0.5, 64, string_index=1, fret=2)]),
        ],
    )

    summary = report.roles[0]
    assert summary.overlap_count == 1
    assert summary.exact_duplicate_count == 1
    overlap = summary.overlaps[0]
    assert overlap.kind == "exact_duplicate"
    assert (overlap.left.source_track_index, overlap.left.event_index) == (1, 0)
    assert (overlap.right.source_track_index, overlap.right.event_index) == (2, 0)


def test_same_onset_different_pitch_is_coincident_not_silently_resolved() -> None:
    report = analyze_score_role_composition_overlaps(
        _plan(1, 2),
        [
            _track(1, [_note(1.0, 0.5, 64)]),
            _track(2, [_note(1.0, 0.25, 67)]),
        ],
    )

    summary = report.roles[0]
    assert summary.coincident_start_count == 1
    assert summary.exact_duplicate_count == 0
    assert summary.overlaps[0].kind == "coincident_start"


def test_sustained_cross_track_intersection_is_reported() -> None:
    report = analyze_score_role_composition_overlaps(
        _plan(1, 2),
        [
            _track(1, [_note(1.0, 2.0, 64)]),
            _track(2, [_note(2.5, 0.75, 67)]),
        ],
    )

    summary = report.roles[0]
    assert summary.duration_overlap_count == 1
    assert summary.overlaps[0].kind == "duration_overlap"


def test_only_cross_track_overlap_is_analyzed() -> None:
    report = analyze_score_role_composition_overlaps(
        _plan(1),
        [
            _track(
                1,
                [
                    _note(1.0, 1.0, 64),
                    _note(1.0, 1.0, 67),
                ],
            )
        ],
    )

    assert report.roles[0].overlap_count == 0


def test_missing_selected_track_fails_closed() -> None:
    with pytest.raises(ValueError, match="missing selected source track"):
        analyze_score_role_composition_overlaps(
            _plan(1, 2),
            [_track(1, [_note(0.0, 0.5, 60)])],
        )


def test_duplicate_supplied_track_identity_fails_closed() -> None:
    with pytest.raises(ValueError, match="unique source track indexes"):
        analyze_score_role_composition_overlaps(
            _plan(1),
            [
                _track(1, [_note(0.0, 0.5, 60)]),
                _track(1, [_note(1.0, 0.5, 62)]),
            ],
        )
