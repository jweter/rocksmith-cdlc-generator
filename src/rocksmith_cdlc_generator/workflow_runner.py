from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict

from .workflow_plan import ProjectWorkflowPlan, WorkflowStep, build_project_workflow_plan


StopReason = Literal[
    "human_gate",
    "complete",
    "step_failed",
    "no_progress",
    "max_steps",
]

_AUTOMATIC_COMMANDS = {
    "normalize",
    "tempo",
    "transcribe-bass",
    "align-source",
    "reconcile-bass",
    "map-bass",
    "validate",
}


class ExecutedWorkflowStep(BaseModel):
    model_config = ConfigDict(frozen=True)

    step_id: str
    command: str
    return_code: int


class AutomaticWorkflowRun(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    project_path: str
    executed_steps: list[ExecutedWorkflowStep]
    stop_reason: StopReason
    next_step_id: str | None
    final_plan: ProjectWorkflowPlan


def _planner_command_argv(command: str) -> list[str]:
    """Convert a planner-owned display command to argv without invoking a shell."""

    parts = shlex.split(command, posix=False)
    argv = [
        part[1:-1] if len(part) >= 2 and part[0] == part[-1] and part[0] in {'"', "'"} else part
        for part in parts
    ]
    if len(argv) < 2 or argv[0] != "cdlc" or argv[1] not in _AUTOMATIC_COMMANDS:
        raise ValueError(f"Planner command is not an approved automatic CDLC operation: {command}")
    return argv


def _default_command_runner(argv: list[str]) -> int:
    process = subprocess.run(
        [sys.executable, "-m", "rocksmith_cdlc_generator.cli", *argv[1:]],
        check=False,
    )
    return process.returncode


def _next_actionable_step(plan: ProjectWorkflowPlan) -> WorkflowStep | None:
    if plan.next_step_id is None:
        return None
    return next((step for step in plan.steps if step.step_id == plan.next_step_id), None)


def run_automatic_first_draft(
    project_dir: Path,
    *,
    max_steps: int = 8,
    plan_builder: Callable[[Path], ProjectWorkflowPlan] = build_project_workflow_plan,
    command_runner: Callable[[list[str]], int] = _default_command_runner,
) -> AutomaticWorkflowRun:
    """Execute deterministic ready steps until the workflow reaches a human gate.

    The planner remains authoritative. This runner never executes a human-mode step,
    never invokes a shell, and only accepts a small whitelist of deterministic CDLC
    subcommands. A validation return code of 2 is expected when validation writes a
    blocking review report; the workflow is replanned so the human review gate can
    become the next action.
    """

    if max_steps < 1:
        raise ValueError("max_steps must be at least 1")

    project = project_dir.expanduser().resolve()
    executed: list[ExecutedWorkflowStep] = []
    plan = plan_builder(project)

    for _ in range(max_steps):
        step = _next_actionable_step(plan)
        if step is None:
            return AutomaticWorkflowRun(
                project_path=str(project),
                executed_steps=executed,
                stop_reason="complete",
                next_step_id=None,
                final_plan=plan,
            )
        if step.mode == "human" or step.status == "blocked":
            return AutomaticWorkflowRun(
                project_path=str(project),
                executed_steps=executed,
                stop_reason="human_gate",
                next_step_id=step.step_id,
                final_plan=plan,
            )
        if step.status != "ready" or step.command is None:
            return AutomaticWorkflowRun(
                project_path=str(project),
                executed_steps=executed,
                stop_reason="no_progress",
                next_step_id=step.step_id,
                final_plan=plan,
            )

        argv = _planner_command_argv(step.command)
        return_code = command_runner(argv)
        executed.append(
            ExecutedWorkflowStep(
                step_id=step.step_id,
                command=step.command,
                return_code=return_code,
            )
        )
        if return_code != 0 and not (step.step_id == "validate" and return_code == 2):
            return AutomaticWorkflowRun(
                project_path=str(project),
                executed_steps=executed,
                stop_reason="step_failed",
                next_step_id=step.step_id,
                final_plan=plan,
            )

        previous_signature = (plan.next_step_id, step.command)
        plan = plan_builder(project)
        next_step = _next_actionable_step(plan)
        if (
            next_step is not None
            and next_step.mode == "automatic"
            and next_step.status == "ready"
            and (plan.next_step_id, next_step.command) == previous_signature
        ):
            return AutomaticWorkflowRun(
                project_path=str(project),
                executed_steps=executed,
                stop_reason="no_progress",
                next_step_id=plan.next_step_id,
                final_plan=plan,
            )

    return AutomaticWorkflowRun(
        project_path=str(project),
        executed_steps=executed,
        stop_reason="max_steps",
        next_step_id=plan.next_step_id,
        final_plan=plan,
    )
