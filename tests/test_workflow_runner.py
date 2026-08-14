from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.workflow_plan import ProjectWorkflowPlan, WorkflowStep
from rocksmith_cdlc_generator.workflow_runner import (
    _planner_command_argv,
    run_automatic_first_draft,
)


def _plan(project: Path, *, step: WorkflowStep | None) -> ProjectWorkflowPlan:
    steps = [] if step is None else [step]
    return ProjectWorkflowPlan(
        project_path=str(project),
        steps=steps,
        next_step_id=None if step is None else step.step_id,
        automatic_ready_steps=sum(s.mode == "automatic" and s.status == "ready" for s in steps),
        human_blocking_steps=sum(s.mode == "human" and s.status == "blocked" for s in steps),
    )


def test_runner_executes_ready_automatic_steps_until_human_gate(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    state = {"stage": 0}

    def planner(_: Path) -> ProjectWorkflowPlan:
        if state["stage"] == 0:
            return _plan(project, step=WorkflowStep(
                step_id="normalize",
                title="Normalize",
                status="ready",
                mode="automatic",
                command=f'cdlc normalize "{project}"',
                reason="ready",
            ))
        if state["stage"] == 1:
            return _plan(project, step=WorkflowStep(
                step_id="tempo",
                title="Tempo",
                status="ready",
                mode="automatic",
                command=f'cdlc tempo "{project}" --engine librosa',
                reason="ready",
            ))
        return _plan(project, step=WorkflowStep(
            step_id="source-rights",
            title="Review rights",
            status="blocked",
            mode="human",
            reason="human confirmation required",
        ))

    calls: list[list[str]] = []

    def runner(argv: list[str]) -> int:
        calls.append(argv)
        state["stage"] += 1
        return 0

    result = run_automatic_first_draft(
        project,
        plan_builder=planner,
        command_runner=runner,
    )

    assert [step.step_id for step in result.executed_steps] == ["normalize", "tempo"]
    assert calls[0][:2] == ["cdlc", "normalize"]
    assert calls[1][:2] == ["cdlc", "tempo"]
    assert result.stop_reason == "human_gate"
    assert result.next_step_id == "source-rights"


def test_runner_never_executes_human_ready_step(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    plan = _plan(project, step=WorkflowStep(
        step_id="human-review",
        title="Review",
        status="ready",
        mode="human",
        command="cdlc validate should-not-run",
        reason="review required",
    ))

    calls: list[list[str]] = []
    result = run_automatic_first_draft(
        project,
        plan_builder=lambda _: plan,
        command_runner=lambda argv: calls.append(argv) or 0,
    )

    assert calls == []
    assert result.stop_reason == "human_gate"
    assert result.next_step_id == "human-review"


def test_validation_exit_two_is_review_outcome_not_runner_failure(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    state = {"validated": False}

    def planner(_: Path) -> ProjectWorkflowPlan:
        if not state["validated"]:
            return _plan(project, step=WorkflowStep(
                step_id="validate",
                title="Validate",
                status="ready",
                mode="automatic",
                command=f'cdlc validate "{project}"',
                reason="ready",
            ))
        return _plan(project, step=WorkflowStep(
            step_id="human-review",
            title="Review",
            status="ready",
            mode="human",
            reason="validation wrote blocking review items",
        ))

    def runner(_: list[str]) -> int:
        state["validated"] = True
        return 2

    result = run_automatic_first_draft(project, plan_builder=planner, command_runner=runner)

    assert result.executed_steps[-1].return_code == 2
    assert result.stop_reason == "human_gate"
    assert result.next_step_id == "human-review"


def test_runner_stops_on_automatic_command_failure(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    plan = _plan(project, step=WorkflowStep(
        step_id="tempo",
        title="Tempo",
        status="ready",
        mode="automatic",
        command=f'cdlc tempo "{project}" --engine librosa',
        reason="ready",
    ))

    result = run_automatic_first_draft(
        project,
        plan_builder=lambda _: plan,
        command_runner=lambda _: 7,
    )

    assert result.stop_reason == "step_failed"
    assert result.executed_steps[-1].return_code == 7


def test_runner_detects_no_progress(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    plan = _plan(project, step=WorkflowStep(
        step_id="normalize",
        title="Normalize",
        status="ready",
        mode="automatic",
        command=f'cdlc normalize "{project}"',
        reason="ready",
    ))

    result = run_automatic_first_draft(
        project,
        plan_builder=lambda _: plan,
        command_runner=lambda _: 0,
    )

    assert result.stop_reason == "no_progress"
    assert len(result.executed_steps) == 1


def test_planner_command_parser_preserves_quoted_windows_paths() -> None:
    argv = _planner_command_argv(
        'cdlc map-bass "C:\\Users\\Jeremy\\My Song" --source auto --tuning "E Standard" --max-fret 24'
    )

    assert argv == [
        "cdlc",
        "map-bass",
        "C:\\Users\\Jeremy\\My Song",
        "--source",
        "auto",
        "--tuning",
        "E Standard",
        "--max-fret",
        "24",
    ]


def test_planner_command_parser_rejects_non_whitelisted_operation() -> None:
    with pytest.raises(ValueError, match="approved automatic"):
        _planner_command_argv("cdlc launch-dlcbuilder project --executable tool.exe")


def test_max_steps_must_be_positive(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        run_automatic_first_draft(tmp_path, max_steps=0)
