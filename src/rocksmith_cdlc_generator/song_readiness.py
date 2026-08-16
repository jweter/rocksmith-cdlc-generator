from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .workflow_plan import ProjectWorkflowPlan, WorkflowStep


class ReadinessAction(BaseModel):
    model_config = ConfigDict(frozen=True)

    step_id: str
    kind: Literal["needs_you", "automatic", "waiting"]
    title: str
    detail: str


class SongReadiness(BaseModel):
    model_config = ConfigDict(frozen=True)

    percent: int = Field(ge=0, le=100)
    completed_steps: int = Field(ge=0)
    required_steps: int = Field(ge=0)
    headline: str
    next_action: ReadinessAction | None
    needs_you: tuple[ReadinessAction, ...]
    automatic_ready: tuple[ReadinessAction, ...]


_FRIENDLY_TITLES = {
    "recording-audio": "Choose the song recording",
    "source-rights": "Confirm you are allowed to use the local song and score files",
    "score-arrangements": "Confirm which score tracks are Bass, Lead, and Rhythm",
    "recording-reference": "Confirm the recording/version when needed",
    "normalize": "Prepare working audio",
    "tempo": "Map the song timing",
    "transcribe-bass": "Create the first Bass draft",
    "align-tab": "Align the score to the recording",
    "shared-timeline": "Review the song timing once for all arrangements",
    "build-lead": "Create the Lead arrangement",
    "build-rhythm": "Create the Rhythm arrangement",
    "human-review": "Review the generated song draft",
}


def _friendly_action(step: WorkflowStep) -> ReadinessAction:
    if step.mode == "human" and step.status in {"blocked", "ready"}:
        kind: Literal["needs_you", "automatic", "waiting"] = "needs_you"
    elif step.mode == "automatic" and step.status == "ready":
        kind = "automatic"
    else:
        kind = "waiting"
    return ReadinessAction(
        step_id=step.step_id,
        kind=kind,
        title=_FRIENDLY_TITLES.get(step.step_id, step.title),
        detail=step.reason,
    )


def _counts_as_progress_complete(step: WorkflowStep) -> bool:
    if step.status == "complete":
        return True
    # The planner deliberately models the terminal review queue as a ready human
    # action rather than a persistable "complete" artifact. Once validation has
    # produced that queue, deterministic authoring preparation is complete even
    # though the review itself must still remain explicit human work.
    return step.step_id == "human-review" and step.status == "ready" and step.mode == "human"


def build_song_readiness(plan: ProjectWorkflowPlan) -> SongReadiness:
    """Translate the internal workflow plan into user-facing progress and next action.

    Optional steps do not affect the percentage. Only the first unresolved required
    step is considered actionable; later blocked steps are dependencies, not requests
    for the user to act early. The terminal human review queue counts as prepared
    progress once it becomes ready, but it still remains an explicit ``Needs you``
    action and grants no review authority.
    """

    required = [step for step in plan.steps if step.status != "optional"]
    completed = [step for step in required if _counts_as_progress_complete(step)]
    percent = 100 if not required else round(100 * len(completed) / len(required))

    unresolved = next((step for step in required if step.status != "complete"), None)
    actionable = _friendly_action(unresolved) if unresolved is not None else None

    needs_you: tuple[ReadinessAction, ...] = ()
    automatic_ready: tuple[ReadinessAction, ...] = ()
    if actionable is not None and actionable.kind == "needs_you":
        needs_you = (actionable,)
    elif actionable is not None and actionable.kind == "automatic":
        automatic_ready = (actionable,)

    if actionable is None:
        headline = "Authoring workflow complete"
        next_action = None
    elif actionable.kind == "needs_you":
        headline = "Needs you: 1 decision"
        next_action = actionable
    elif actionable.kind == "automatic":
        headline = "Ready to continue automatically"
        next_action = actionable
    else:
        headline = "Waiting for earlier steps to finish"
        next_action = actionable

    return SongReadiness(
        percent=percent,
        completed_steps=len(completed),
        required_steps=len(required),
        headline=headline,
        next_action=next_action,
        needs_you=needs_you,
        automatic_ready=automatic_ready,
    )
