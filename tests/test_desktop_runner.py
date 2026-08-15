from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator import desktop_runner
from rocksmith_cdlc_generator.workflow_runner import _planner_command_argv


def test_score_fanout_is_approved_automatic_entrypoint() -> None:
    assert _planner_command_argv('cdlc-score-fanout "C:\\Songs\\Demo"') == [
        "cdlc-score-fanout",
        "C:\\Songs\\Demo",
    ]


def test_desktop_runner_dispatches_score_fanout_in_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    called: list[Path] = []
    monkeypatch.setattr(
        desktop_runner,
        "fanout_confirmed_score_mappings",
        lambda project: called.append(project),
    )

    result = desktop_runner.desktop_command_runner(["cdlc-score-fanout", str(tmp_path)])

    assert result == 0
    assert called == [tmp_path.resolve()]


def test_desktop_runner_never_accepts_arbitrary_programs(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported desktop workflow command"):
        desktop_runner.desktop_command_runner(["powershell", "-Command", "Write-Host unsafe"])


def test_desktop_runner_preserves_validation_review_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Report:
        can_package = False

    monkeypatch.setattr(desktop_runner, "validate_project", lambda project: Report())
    monkeypatch.setattr(desktop_runner, "validate_project_to_disk", lambda project: tmp_path / "report.json")

    assert desktop_runner.desktop_command_runner(["cdlc", "validate", str(tmp_path)]) == 2
