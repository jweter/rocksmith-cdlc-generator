from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator import workflow_runner_cli
from rocksmith_cdlc_generator.workflow_plan import ProjectWorkflowPlan
from rocksmith_cdlc_generator.workflow_runner import AutomaticWorkflowRun


def _result(project: Path, *, stop_reason: str) -> AutomaticWorkflowRun:
    plan = ProjectWorkflowPlan(
        project_path=str(project),
        steps=[],
        next_step_id=None,
        automatic_ready_steps=0,
        human_blocking_steps=0,
    )
    return AutomaticWorkflowRun(
        project_path=str(project),
        executed_steps=[],
        stop_reason=stop_reason,
        next_step_id=None,
        final_plan=plan,
    )


@pytest.mark.parametrize("reason", ["step_failed", "no_progress"])
def test_cli_returns_nonzero_for_runner_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    reason: str,
) -> None:
    project = tmp_path / "song"
    monkeypatch.setattr(
        workflow_runner_cli,
        "run_automatic_first_draft",
        lambda *_args, **_kwargs: _result(project, stop_reason=reason),
    )
    monkeypatch.setattr("sys.argv", ["cdlc-auto", str(project)])

    assert workflow_runner_cli.main() == 1


@pytest.mark.parametrize("reason", ["human_gate", "complete", "max_steps"])
def test_cli_returns_zero_for_expected_stops(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    reason: str,
) -> None:
    project = tmp_path / "song"
    monkeypatch.setattr(
        workflow_runner_cli,
        "run_automatic_first_draft",
        lambda *_args, **_kwargs: _result(project, stop_reason=reason),
    )
    monkeypatch.setattr("sys.argv", ["cdlc-auto", str(project)])

    assert workflow_runner_cli.main() == 0
