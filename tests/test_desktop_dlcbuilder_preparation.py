from pathlib import Path

import pytest

from rocksmith_cdlc_generator.desktop_dlcbuilder_window import (
    DlcBuilderPreparationWindow,
    parse_preview_start,
)
from rocksmith_cdlc_generator.desktop_shell import ProductDesktopApp


class _Status:
    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value


class _Text:
    def __init__(self, value: str) -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class _PrepareRequest:
    def __init__(self, accepted: bool) -> None:
        self.accepted = accepted
        self.args = None

    def __call__(self, preview_start, dlc_key, success, failure) -> bool:
        self.args = (preview_start, dlc_key, success, failure)
        return self.accepted


def test_parse_preview_start() -> None:
    assert parse_preview_start(" 12.5 ") == 12.5
    with pytest.raises(ValueError, match="required"):
        parse_preview_start(" ")
    with pytest.raises(ValueError, match="number"):
        parse_preview_start("intro")
    with pytest.raises(ValueError, match="finite"):
        parse_preview_start("nan")
    with pytest.raises(ValueError, match="finite"):
        parse_preview_start("inf")
    with pytest.raises(ValueError, match="finite"):
        parse_preview_start("-inf")
    with pytest.raises(ValueError, match="non-negative"):
        parse_preview_start("-1")


def test_project_switch_clears_project_specific_form_values(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    window = object.__new__(DlcBuilderPreparationWindow)
    window.project = first.resolve()
    window.preview_start_var = _Text("18.5")
    window.dlc_key_var = _Text("FirstSong")
    window.status_var = _Status()

    DlcBuilderPreparationWindow.set_project(window, second)

    assert window.project == second.resolve()
    assert window.preview_start_var.get() == "30.0"
    assert window.dlc_key_var.get() == ""
    assert "not prepared" in window.status_var.value.lower()


def test_same_project_refresh_preserves_unsaved_form_values(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    window = object.__new__(DlcBuilderPreparationWindow)
    window.project = project.resolve()
    window.preview_start_var = _Text("18.5")
    window.dlc_key_var = _Text("MySong")
    window.status_var = _Status()

    DlcBuilderPreparationWindow.set_project(window, project)

    assert window.preview_start_var.get() == "18.5"
    assert window.dlc_key_var.get() == "MySong"


def test_window_does_not_mark_rejected_prepare_request_running() -> None:
    request = _PrepareRequest(False)
    window = object.__new__(DlcBuilderPreparationWindow)
    window.preview_start_var = _Text("30")
    window.dlc_key_var = _Text("MySong")
    window.status_var = _Status()
    window._prepare_request = request

    DlcBuilderPreparationWindow._request(window)

    assert request.args is not None
    assert request.args[0] == 30.0
    assert request.args[1] == "MySong"
    assert "not started" in window.status_var.value.lower()


def test_window_reports_success_and_failure() -> None:
    window = object.__new__(DlcBuilderPreparationWindow)
    window.status_var = _Status()

    destination = Path("build/dlcbuilder/song.rs2dlc")
    DlcBuilderPreparationWindow._succeeded(window, destination)
    assert str(destination) in window.status_var.value

    DlcBuilderPreparationWindow._failed(window, ValueError("validation blocked"))
    assert "preparation failed" in window.status_var.value.lower()
    assert "validation blocked" in window.status_var.value.lower()


class _Shell:
    def __init__(self, project: Path) -> None:
        self.project = project
        self.success_callback = None
        self.failure_callback = None
        self.ui_guard = None
        self.operation = None

    def _run_background(
        self,
        label,
        operation,
        on_success,
        on_failure,
        ui_guard,
    ) -> bool:
        self.operation = operation
        self.success_callback = on_success
        self.failure_callback = on_failure
        self.ui_guard = ui_guard
        return True


def test_prepare_request_callbacks_are_project_bound(tmp_path: Path) -> None:
    original = tmp_path / "first"
    replacement = tmp_path / "second"
    original.mkdir()
    replacement.mkdir()
    shell = _Shell(original)
    successes = []
    failures = []

    accepted = ProductDesktopApp._request_dlcbuilder_prepare(
        shell,
        18.0,
        "SongKey",
        successes.append,
        failures.append,
    )

    assert accepted is True
    assert shell.ui_guard is not None
    assert shell.ui_guard() is True

    shell.project = replacement
    assert shell.ui_guard() is False
    assert shell.success_callback is not None
    assert shell.failure_callback is not None
    shell.success_callback(original / "build" / "dlcbuilder" / "SongKey.rs2dlc")
    shell.failure_callback(ValueError("late failure"))

    assert successes == []
    assert failures == []
