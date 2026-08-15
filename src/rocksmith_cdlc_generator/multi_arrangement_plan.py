from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from .score_mapping_review import load_score_for_mapping_review
from .score_source import ArrangementRole
from .shared_guitar import shared_guitar_draft_is_current
from .shared_timeline import load_current_shared_timeline
from .workflow_plan import (
    ProjectWorkflowPlan,
    WorkflowStep,
    _current_score_fanout,
    build_project_workflow_plan,
)


def _confirmed_guitar_roles(project: Path) -> list[ArrangementRole]:
    try:
        score = load_score_for_mapping_review(project)
        fanout = _current_score_fanout(project, score)
    except (OSError, ValueError, ValidationError):
        return []
    if fanout is None:
        return []
    available = {entry.role for entry in fanout.arrangements}
    return [
        role
        for role in (ArrangementRole.lead, ArrangementRole.rhythm)
        if role in available
        and (mapping := score.mapping_for(role)) is not None
        and mapping.human_confirmed
    ]


def _shared_timeline_is_current(project: Path) -> bool:
    try:
        load_current_shared_timeline(project)
    except (OSError, ValueError, ValidationError):
        return False
    return True


def build_multi_arrangement_workflow_plan(project_dir: Path) -> ProjectWorkflowPlan:
    """Extend the proven Bass workflow into one shared-timeline three-arrangement plan.

    The existing planner remains the source of truth for recording, rights, score fan-out,
    Bass alignment/reconciliation, and review gates. This layer adds only the product-level
    transition that follows a human-reviewed shared-score Bass alignment: one explicit
    shared-timeline promotion, then deterministic Lead/Rhythm chart construction from that
    same timing authority.
    """

    base = build_project_workflow_plan(project_dir)
    project = Path(base.project_path).resolve()
    guitar_roles = _confirmed_guitar_roles(project)
    if not guitar_roles:
        return base

    steps = list(base.steps)
    align_index = next((index for index, step in enumerate(steps) if step.step_id == "align-tab"), None)
    if align_index is None:
        return base

    project_q = f'"{project}"'
    alignment_complete = steps[align_index].status == "complete"
    timeline_current = _shared_timeline_is_current(project)

    if timeline_current:
        timeline_step = WorkflowStep(
            step_id="shared-timeline",
            title="Shared song timing reviewed",
            status="complete",
            mode="human",
            reason=(
                "One reviewed score-to-recording timeline is current and is inherited by "
                + ", ".join(role.value for role in guitar_roles)
                + " alongside Bass."
            ),
        )
    elif alignment_complete:
        timeline_step = WorkflowStep(
            step_id="shared-timeline",
            title="Review and promote shared song timing",
            status="blocked",
            mode="human",
            command=f"cdlc-shared-timeline promote {project_q}",
            reason=(
                "The authoritative shared-score Bass projection is aligned. Review that timing once, "
                "then promote it so Bass, Lead, and Rhythm inherit one song timeline."
            ),
        )
    else:
        timeline_step = WorkflowStep(
            step_id="shared-timeline",
            title="Establish shared song timing",
            status="blocked",
            mode="automatic",
            reason="Shared timing waits for the authoritative shared-score Bass projection to be aligned to the recording.",
        )

    guitar_steps: list[WorkflowStep] = []
    for role in guitar_roles:
        current = timeline_current and shared_guitar_draft_is_current(project, role.value)
        guitar_steps.append(
            WorkflowStep(
                step_id=f"build-{role.value}",
                title=f"Build {role.value.title()} from shared timeline",
                status="complete" if current else ("ready" if timeline_current else "blocked"),
                mode="automatic",
                command=(
                    None
                    if current or not timeline_current
                    else f"cdlc-build-shared-guitar {project_q} --instrument {role.value}"
                ),
                reason=(
                    f"The current {role.value.title()} draft is provenance-bound to the reviewed shared timeline and confirmed score track."
                    if current
                    else (
                        f"Project the human-confirmed {role.value.title()} score track through the already reviewed shared song timeline; no second alignment is required."
                        if timeline_current
                        else f"{role.value.title()} construction waits for the shared song timeline review."
                    )
                ),
            )
        )

    # Timing authority belongs immediately after the one alignment step. This makes the
    # planner visibly transition from 'align once' to parallel arrangement construction
    # instead of hiding guitar work after the Bass-only review tail.
    insertion = align_index + 1
    steps[insertion:insertion] = [timeline_step, *guitar_steps]

    next_step = next((step.step_id for step in steps if step.status in {"blocked", "ready"}), None)
    automatic_ready = sum(step.status == "ready" and step.mode == "automatic" for step in steps)
    human_blocking = sum(step.status == "blocked" and step.mode == "human" for step in steps)
    return ProjectWorkflowPlan(
        project_path=base.project_path,
        steps=steps,
        next_step_id=next_step,
        automatic_ready_steps=automatic_ready,
        human_blocking_steps=human_blocking,
    )
