from __future__ import annotations

import pytest
from pydantic import ValidationError

from rocksmith_cdlc_generator.score_role_composition_overlap import (
    CompositionNoteReference,
    CompositionOverlap,
    RoleCompositionOverlapSummary,
    ScoreRoleCompositionOverlapReport,
)
from rocksmith_cdlc_generator.score_role_composition_overlap_review import (
    CompositionOverlapDecision,
    ScoreRoleCompositionOverlapDecisionPlan,
    build_score_role_composition_overlap_decision_plan,
    unresolved_composition_overlap_count,
    validate_score_role_composition_overlap_decisions,
)
from rocksmith_cdlc_generator.score_source import ArrangementRole


def _ref(track: int, event: int, *, start: float, midi: int) -> CompositionNoteReference:
    return CompositionNoteReference(
        source_track_index=track,
        event_index=event,
        start_seconds=start,
        duration_seconds=0.5,
        midi=midi,
        string_index=0,
        fret=midi - 40,
    )


def _report() -> ScoreRoleCompositionOverlapReport:
    duplicate = CompositionOverlap(
        kind="exact_duplicate",
        left=_ref(1, 0, start=1.0, midi=52),
        right=_ref(4, 3, start=1.0, midi=52),
    )
    chord_candidate = CompositionOverlap(
        kind="coincident_start",
        left=_ref(1, 1, start=2.0, midi=55),
        right=_ref(4, 4, start=2.0, midi=59),
    )
    return ScoreRoleCompositionOverlapReport(
        score_sha256="a" * 64,
        score_format="gp5",
        roles=[
            RoleCompositionOverlapSummary(
                role=ArrangementRole.lead,
                source_track_indices=[1, 4],
                overlap_count=2,
                exact_duplicate_count=1,
                coincident_start_count=1,
                duration_overlap_count=0,
                overlaps=[duplicate, chord_candidate],
            )
        ],
    )


def test_accepts_partial_human_overlap_decisions_and_counts_unresolved() -> None:
    report = _report()
    decision = CompositionOverlapDecision(
        role=ArrangementRole.lead,
        overlap=report.roles[0].overlaps[0],
        resolution="keep_left",
    )

    plan = build_score_role_composition_overlap_decision_plan(report, [decision])

    assert plan.decisions == [decision]
    assert unresolved_composition_overlap_count(report, plan) == 1


def test_keep_both_is_recorded_without_resolving_other_overlap_findings() -> None:
    report = _report()
    decision = CompositionOverlapDecision(
        role=ArrangementRole.lead,
        overlap=report.roles[0].overlaps[1],
        resolution="keep_both",
    )

    plan = build_score_role_composition_overlap_decision_plan(report, [decision])

    assert plan.decisions[0].resolution == "keep_both"
    assert unresolved_composition_overlap_count(report, plan) == 1
    assert report.roles[0].overlap_count == 2


def test_rejects_stale_score_provenance() -> None:
    report = _report()
    plan = ScoreRoleCompositionOverlapDecisionPlan(
        score_sha256="b" * 64,
        score_format="gp5",
    )

    with pytest.raises(ValueError, match="stale"):
        validate_score_role_composition_overlap_decisions(report, plan)


def test_rejects_decision_when_overlap_evidence_changed() -> None:
    report = _report()
    changed = report.roles[0].overlaps[0].model_copy(
        update={"left": report.roles[0].overlaps[0].left.model_copy(update={"midi": 53})}
    )
    plan = ScoreRoleCompositionOverlapDecisionPlan(
        score_sha256=report.score_sha256,
        score_format=report.score_format,
        decisions=[
            CompositionOverlapDecision(
                role=ArrangementRole.lead,
                overlap=changed,
                resolution="keep_right",
            )
        ],
    )

    with pytest.raises(ValueError, match="does not match a current reported overlap"):
        validate_score_role_composition_overlap_decisions(report, plan)


def test_rejects_duplicate_decisions_for_same_overlap() -> None:
    report = _report()
    overlap = report.roles[0].overlaps[0]

    with pytest.raises(ValidationError, match="duplicate decisions"):
        ScoreRoleCompositionOverlapDecisionPlan(
            score_sha256=report.score_sha256,
            score_format=report.score_format,
            decisions=[
                CompositionOverlapDecision(
                    role=ArrangementRole.lead,
                    overlap=overlap,
                    resolution="keep_left",
                ),
                CompositionOverlapDecision(
                    role=ArrangementRole.lead,
                    overlap=overlap,
                    resolution="keep_right",
                ),
            ],
        )
