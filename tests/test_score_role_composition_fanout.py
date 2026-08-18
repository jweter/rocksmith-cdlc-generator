from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.score_role_composition import (
    ScoreRoleCompositionPlan,
    ScoreRoleCompositionSelection,
)
from rocksmith_cdlc_generator.score_role_composition_fanout import compose_role_notes
from rocksmith_cdlc_generator.score_role_composition_overlap import (
    analyze_score_role_composition_overlaps,
)
from rocksmith_cdlc_generator.score_role_composition_overlap_review import (
    CompositionOverlapDecision,
    ScoreRoleCompositionOverlapDecisionPlan,
)
from rocksmith_cdlc_generator.score_source import ArrangementRole
from rocksmith_cdlc_generator.source_import import SourceNoteEvent, SourceTrack

_SCORE_SHA = "a" * 64


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
    return SourceTrack(source_track_index=index, name=f"Track {index}", instrument="guitar", notes=notes)


def _plan(role: ArrangementRole, *indexes: int) -> ScoreRoleCompositionPlan:
    return ScoreRoleCompositionPlan(
        score_sha256=_SCORE_SHA,
        score_format="gp5",
        selections=[ScoreRoleCompositionSelection(role=role, source_track_indices=list(indexes))],
    )


def _empty_decisions() -> ScoreRoleCompositionOverlapDecisionPlan:
    return ScoreRoleCompositionOverlapDecisionPlan(score_sha256=_SCORE_SHA, score_format="gp5")


def test_composes_non_overlapping_tracks_in_time_order() -> None:
    plan = _plan(ArrangementRole.lead, 1, 2)
    tracks = [
        _track(1, [_note(0.5, 0.5, 60)]),
        _track(2, [_note(0.0, 0.25, 55)]),
    ]

    result = compose_role_notes(plan, _empty_decisions(), tracks, role=ArrangementRole.lead)

    assert [(n.source_track_index, n.event_index) for n in result.notes] == [(2, 0), (1, 0)]
    assert result.source_track_indices == [1, 2]
    assert result.score_sha256 == _SCORE_SHA


def test_unresolved_overlap_fails_closed() -> None:
    plan = _plan(ArrangementRole.lead, 1, 4)
    tracks = [
        _track(1, [_note(1.0, 0.5, 52)]),
        _track(4, [_note(1.0, 0.5, 52)]),
    ]

    with pytest.raises(ValueError, match="unresolved overlap"):
        compose_role_notes(plan, _empty_decisions(), tracks, role=ArrangementRole.lead)


def test_keep_left_drops_the_losing_right_note() -> None:
    plan = _plan(ArrangementRole.lead, 1, 4)
    tracks = [
        _track(1, [_note(1.0, 0.5, 52)]),
        _track(4, [_note(1.0, 0.5, 52)]),
    ]
    report = analyze_score_role_composition_overlaps(plan, tracks)
    decisions = ScoreRoleCompositionOverlapDecisionPlan(
        score_sha256=_SCORE_SHA,
        score_format="gp5",
        decisions=[
            CompositionOverlapDecision(
                role=ArrangementRole.lead, overlap=report.roles[0].overlaps[0], resolution="keep_left"
            )
        ],
    )

    result = compose_role_notes(plan, decisions, tracks, role=ArrangementRole.lead)

    assert [(n.source_track_index, n.event_index) for n in result.notes] == [(1, 0)]


def test_keep_right_drops_the_losing_left_note() -> None:
    plan = _plan(ArrangementRole.lead, 1, 4)
    tracks = [
        _track(1, [_note(1.0, 0.5, 52)]),
        _track(4, [_note(1.0, 0.5, 52)]),
    ]
    report = analyze_score_role_composition_overlaps(plan, tracks)
    decisions = ScoreRoleCompositionOverlapDecisionPlan(
        score_sha256=_SCORE_SHA,
        score_format="gp5",
        decisions=[
            CompositionOverlapDecision(
                role=ArrangementRole.lead, overlap=report.roles[0].overlaps[0], resolution="keep_right"
            )
        ],
    )

    result = compose_role_notes(plan, decisions, tracks, role=ArrangementRole.lead)

    assert [(n.source_track_index, n.event_index) for n in result.notes] == [(4, 0)]


def test_keep_both_preserves_a_reviewed_chord_candidate() -> None:
    plan = _plan(ArrangementRole.lead, 1, 4)
    tracks = [
        _track(1, [_note(2.0, 0.5, 55)]),
        _track(4, [_note(2.0, 0.5, 59)]),
    ]
    report = analyze_score_role_composition_overlaps(plan, tracks)
    decisions = ScoreRoleCompositionOverlapDecisionPlan(
        score_sha256=_SCORE_SHA,
        score_format="gp5",
        decisions=[
            CompositionOverlapDecision(
                role=ArrangementRole.lead, overlap=report.roles[0].overlaps[0], resolution="keep_both"
            )
        ],
    )

    result = compose_role_notes(plan, decisions, tracks, role=ArrangementRole.lead)

    assert {(n.source_track_index, n.event_index) for n in result.notes} == {(1, 0), (4, 0)}


def test_a_note_referenced_as_a_losing_side_stays_excluded_even_with_a_conflicting_decision() -> None:
    # Track 1 note overlaps both track 2 and track 3. One decision keeps track 1's note,
    # the other explicitly discards it; exclusion wins so nothing is silently kept.
    plan = _plan(ArrangementRole.rhythm, 1, 2, 3)
    tracks = [
        _track(1, [_note(0.0, 1.0, 40)]),
        _track(2, [_note(0.0, 1.0, 45)]),
        _track(3, [_note(0.0, 1.0, 50)]),
    ]
    report = analyze_score_role_composition_overlaps(plan, tracks)
    overlaps = report.roles[0].overlaps
    left_wins = next(o for o in overlaps if o.left.source_track_index == 1 and o.right.source_track_index == 2)
    left_loses = next(o for o in overlaps if o.left.source_track_index == 1 and o.right.source_track_index == 3)
    remaining = next(o for o in overlaps if o.left.source_track_index == 2 and o.right.source_track_index == 3)
    decisions = ScoreRoleCompositionOverlapDecisionPlan(
        score_sha256=_SCORE_SHA,
        score_format="gp5",
        decisions=[
            CompositionOverlapDecision(role=ArrangementRole.rhythm, overlap=left_wins, resolution="keep_left"),
            CompositionOverlapDecision(role=ArrangementRole.rhythm, overlap=left_loses, resolution="keep_right"),
            CompositionOverlapDecision(role=ArrangementRole.rhythm, overlap=remaining, resolution="keep_both"),
        ],
    )

    result = compose_role_notes(plan, decisions, tracks, role=ArrangementRole.rhythm)

    produced = {(n.source_track_index, n.event_index) for n in result.notes}
    # Track 1's note is the winner of one decision (`left_wins`) but the explicit loser
    # of another (`left_loses`); exclusion wins so it is never silently reintroduced.
    # Track 2's note loses `left_wins`, so only track 3's note remains.
    assert (1, 0) not in produced
    assert produced == {(3, 0)}


def test_unknown_role_fails_closed() -> None:
    plan = _plan(ArrangementRole.lead, 1)
    tracks = [_track(1, [_note(0.0, 0.5, 60)])]

    with pytest.raises(ValueError, match="no current composition selection"):
        compose_role_notes(plan, _empty_decisions(), tracks, role=ArrangementRole.rhythm)


def test_stale_decision_plan_fails_closed() -> None:
    plan = _plan(ArrangementRole.lead, 1, 4)
    tracks = [
        _track(1, [_note(1.0, 0.5, 52)]),
        _track(4, [_note(1.0, 0.5, 52)]),
    ]
    report = analyze_score_role_composition_overlaps(plan, tracks)
    stale_decisions = ScoreRoleCompositionOverlapDecisionPlan(
        score_sha256="b" * 64,
        score_format="gp5",
        decisions=[],
    )
    # Even a matching decision built against a differently-hashed plan must fail closed.
    with pytest.raises(ValueError, match="stale"):
        compose_role_notes(plan, stale_decisions, tracks, role=ArrangementRole.lead)
    assert report.score_sha256 == _SCORE_SHA


def test_decisions_for_other_roles_do_not_leak_into_this_composition() -> None:
    plan = _plan(ArrangementRole.lead, 1, 4)
    tracks = [
        _track(1, [_note(1.0, 0.5, 52)]),
        _track(4, [_note(1.0, 0.5, 52)]),
    ]
    report = analyze_score_role_composition_overlaps(plan, tracks)
    # A decision for a different role than the one currently reported must not resolve
    # this role's overlap.
    decisions = ScoreRoleCompositionOverlapDecisionPlan(
        score_sha256=_SCORE_SHA,
        score_format="gp5",
        decisions=[
            CompositionOverlapDecision(
                role=ArrangementRole.rhythm, overlap=report.roles[0].overlaps[0], resolution="keep_left"
            )
        ],
    )

    with pytest.raises(ValueError, match="unresolved overlap"):
        compose_role_notes(plan, decisions, tracks, role=ArrangementRole.lead)
