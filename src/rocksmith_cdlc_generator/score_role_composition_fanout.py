from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .score_role_composition import ScoreRoleCompositionPlan
from .score_role_composition_overlap import (
    CompositionOverlap,
    ScoreRoleCompositionOverlapReport,
    analyze_score_role_composition_overlaps,
)
from .score_role_composition_overlap_review import (
    ScoreRoleCompositionOverlapDecisionPlan,
    validate_score_role_composition_overlap_decisions,
)
from .score_source import ArrangementRole
from .source_import import SourceNoteEvent, SourceTrack


class ComposedSourceNote(BaseModel):
    """One composed note paired with its exact originating source-track/event identity."""

    model_config = ConfigDict(frozen=True)

    source_track_index: int = Field(ge=0)
    event_index: int = Field(ge=0)
    note: SourceNoteEvent


class RoleCompositionResult(BaseModel):
    """Deterministic composed note stream for one Rocksmith role.

    This is a read-only merge result. It grants no timing, technique, chord, tone,
    validation, or export authority, does not write project files, and does not
    change score fan-out, source-rights, or packaging state.
    """

    model_config = ConfigDict(frozen=True)

    role: ArrangementRole
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_format: str
    source_track_indices: list[int]
    notes: list[ComposedSourceNote] = Field(default_factory=list)


def _overlap_signature(overlap: CompositionOverlap) -> tuple[object, ...]:
    left = overlap.left
    right = overlap.right
    return (
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


def _role_scoped_overlap_report(
    plan: ScoreRoleCompositionPlan,
    tracks: list[SourceTrack],
    *,
    role: ArrangementRole,
) -> ScoreRoleCompositionOverlapReport:
    selection = plan.selection_for(role)
    if selection is None:
        raise ValueError(f"{role.value} has no current composition selection")

    scoped_plan = ScoreRoleCompositionPlan(
        score_sha256=plan.score_sha256,
        score_format=plan.score_format,
        selections=[selection],
    )
    return analyze_score_role_composition_overlaps(scoped_plan, tracks)


def compose_role_notes(
    plan: ScoreRoleCompositionPlan,
    decisions: ScoreRoleCompositionOverlapDecisionPlan,
    tracks: list[SourceTrack],
    *,
    role: ArrangementRole,
) -> RoleCompositionResult:
    """Merge validated multi-track selections into one composed note stream.

    Every cross-track overlap currently reported for the requested role must already
    carry an explicit human decision recorded against that exact overlap evidence.
    Composition fails closed for an unknown role, a stale/mismatched decision plan, a
    missing selected source track, or any unresolved overlap rather than guessing which
    musical material to keep. ``keep_both`` never drops a note; ``keep_left``/``keep_right``
    drop only the exact losing note identified by that specific overlap finding, so a
    note referenced as the losing side of any decision is excluded even if a different
    overlap decision would otherwise have kept it.
    """

    selection = plan.selection_for(role)
    if selection is None:
        raise ValueError(f"{role.value} has no current composition selection")

    report = _role_scoped_overlap_report(plan, tracks, role=role)

    role_decisions = ScoreRoleCompositionOverlapDecisionPlan(
        score_sha256=decisions.score_sha256,
        score_format=decisions.score_format,
        decisions=[decision for decision in decisions.decisions if decision.role is role],
    )
    validate_score_role_composition_overlap_decisions(report, role_decisions)

    role_summary = next((summary for summary in report.roles if summary.role is role), None)
    role_overlaps = role_summary.overlaps if role_summary is not None else []

    decisions_by_overlap = {
        _overlap_signature(decision.overlap): decision for decision in role_decisions.decisions
    }

    unresolved = [
        overlap for overlap in role_overlaps if _overlap_signature(overlap) not in decisions_by_overlap
    ]
    if unresolved:
        raise ValueError(
            f"{role.value} composition has {len(unresolved)} unresolved overlap finding(s); "
            "record an explicit human decision for each before composing."
        )

    excluded: set[tuple[int, int]] = set()
    for overlap in role_overlaps:
        decision = decisions_by_overlap[_overlap_signature(overlap)]
        if decision.resolution == "keep_left":
            excluded.add((overlap.right.source_track_index, overlap.right.event_index))
        elif decision.resolution == "keep_right":
            excluded.add((overlap.left.source_track_index, overlap.left.event_index))
        # keep_both discards nothing.

    # `_role_scoped_overlap_report` above already fails closed if any selected track for
    # this role is missing from `tracks`, so lookups below are guaranteed to succeed.
    tracks_by_index = {track.source_track_index: track for track in tracks}
    track_order = {index: position for position, index in enumerate(selection.source_track_indices)}

    composed: list[ComposedSourceNote] = []
    for track_index in selection.source_track_indices:
        track = tracks_by_index[track_index]
        for event_index, note in enumerate(track.notes):
            if (track_index, event_index) in excluded:
                continue
            composed.append(
                ComposedSourceNote(source_track_index=track_index, event_index=event_index, note=note)
            )

    composed.sort(
        key=lambda item: (item.note.start_seconds, track_order[item.source_track_index], item.event_index)
    )

    return RoleCompositionResult(
        role=role,
        score_sha256=plan.score_sha256,
        score_format=plan.score_format,
        source_track_indices=list(selection.source_track_indices),
        notes=composed,
    )
