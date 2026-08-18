from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .score_role_composition_overlap import CompositionOverlap, ScoreRoleCompositionOverlapReport
from .score_source import ArrangementRole

OverlapResolution = Literal["keep_both", "keep_left", "keep_right"]


class CompositionOverlapDecision(BaseModel):
    """One explicit human decision for one exact reported cross-track overlap."""

    model_config = ConfigDict(frozen=True)

    role: ArrangementRole
    overlap: CompositionOverlap
    resolution: OverlapResolution


class ScoreRoleCompositionOverlapDecisionPlan(BaseModel):
    """Provenance-bound human decisions over an exact composition overlap report.

    The plan records review authority only. It does not mutate source notes, merge tracks,
    delete duplicates, create chords, shorten durations, or change fan-out/export state.
    Decisions may be partial so unresolved overlaps remain explicit and reviewable.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_format: str
    decisions: list[CompositionOverlapDecision] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_overlap_decisions(self) -> "ScoreRoleCompositionOverlapDecisionPlan":
        keys = [_decision_identity(decision) for decision in self.decisions]
        if len(keys) != len(set(keys)):
            raise ValueError("composition overlap review contains duplicate decisions")
        return self


def _overlap_identity(role: ArrangementRole, overlap: CompositionOverlap) -> tuple[object, ...]:
    left = overlap.left
    right = overlap.right
    return (
        role.value,
        overlap.kind,
        left.source_track_index,
        left.event_index,
        left.start_seconds,
        left.duration_seconds,
        left.midi,
        left.string_index,
        left.fret,
        right.source_track_index,
        right.event_index,
        right.start_seconds,
        right.duration_seconds,
        right.midi,
        right.string_index,
        right.fret,
    )


def _decision_identity(decision: CompositionOverlapDecision) -> tuple[object, ...]:
    return _overlap_identity(decision.role, decision.overlap)


def validate_score_role_composition_overlap_decisions(
    report: ScoreRoleCompositionOverlapReport,
    plan: ScoreRoleCompositionOverlapDecisionPlan,
) -> ScoreRoleCompositionOverlapDecisionPlan:
    """Fail closed unless every decision matches one exact current reported overlap."""

    if plan.score_sha256 != report.score_sha256 or plan.score_format != report.score_format:
        raise ValueError("composition overlap review is stale for the current overlap report")

    current = {
        _overlap_identity(role_summary.role, overlap)
        for role_summary in report.roles
        for overlap in role_summary.overlaps
    }
    for decision in plan.decisions:
        if _decision_identity(decision) not in current:
            raise ValueError(
                f"{decision.role.value} overlap decision does not match a current reported overlap"
            )
    return plan


def build_score_role_composition_overlap_decision_plan(
    report: ScoreRoleCompositionOverlapReport,
    decisions: list[CompositionOverlapDecision],
) -> ScoreRoleCompositionOverlapDecisionPlan:
    """Build validated partial human decisions for the current overlap evidence."""

    plan = ScoreRoleCompositionOverlapDecisionPlan(
        score_sha256=report.score_sha256,
        score_format=report.score_format,
        decisions=list(decisions),
    )
    return validate_score_role_composition_overlap_decisions(report, plan)


def unresolved_composition_overlap_count(
    report: ScoreRoleCompositionOverlapReport,
    plan: ScoreRoleCompositionOverlapDecisionPlan,
) -> int:
    """Return how many current overlap findings still lack an explicit human decision."""

    validate_score_role_composition_overlap_decisions(report, plan)
    reviewed = {_decision_identity(decision) for decision in plan.decisions}
    total = sum(len(role_summary.overlaps) for role_summary in report.roles)
    return total - len(reviewed)
