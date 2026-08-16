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
}


def _friendly_action(step: WorkflowStep) -> ReadinessAction:
    if step.mode == "human" and step.status == "blocked":
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


def build_song_readiness(plan: ProjectWorkflowPlan) -> SongReadiness:
    """Translate the internal workflow plan into a user-facing progress summary.

    Optional workflow steps are deliberately excluded from the percentage so optional
    recording-reference helpers cannot make an otherwise complete authoring path look
    unfinished. This model owns presentation only; it grants no musical or review authority.
    """

    required = [step for step in plan.steps if step.status != "optional"]
    completed = [step for step in required if step.status == "complete"]
    percent = 100 if not required else round(100 * len(completed) / len(required))

    needs_you = tuple(
        _friendly_action(step)
        for step in required
        if step.status == "blocked" and step.mode == "human"
    )
    automatic_ready = tuple(
        _friendly_action(step)
        for step in required
        if step.status == "ready" and step.mode == "automatic"
    )

    if needs_you:
        headline = f"Needs you: {len(needs_you)} decision{'s' if len(needs_you) != 1 else ''}"
        next_action = needs_you[0]
    elif automatic_ready:
        headline = "Ready to continue automatically"
        next_action = automatic_ready[0]
    elif len(completed) == len(required):
        headline = "Authoring workflow complete"
        next_action = None
    else:
        headline = "Waiting for earlier steps to finish"
        next_step = next((step for step in required if step.status != "complete"), None)
        next_action = _friendly_action(next_step) if next_step is not None else None

    return SongReadiness(
        percent=percent,
        completed_steps=len(completed),
        required_steps=len(required),
        headline=headline,
        next_action=next_action,
        needs_you=needs_you,
        automatic_ready=automatic_ready,
    )
