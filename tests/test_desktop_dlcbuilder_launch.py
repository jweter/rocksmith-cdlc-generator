from pathlib import Path

import pytest

from rocksmith_cdlc_generator.desktop_dlcbuilder_tools import (
    DLCBUILDER_EXE_ENV,
    discover_dlcbuilder_executable,
    require_dlcbuilder_executable,
)
from rocksmith_cdlc_generator.desktop_dlcbuilder_window import DlcBuilderPreparationWindow
from rocksmith_cdlc_generator.desktop_shell import ProductDesktopApp


class _Text:
    def __init__(self, value: str) -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class _Status:
    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value


class _LaunchRequest:
    def __init__(self, accepted: bool) -> None:
        self.accepted = accepted
        self.args = None

    def __call__(self, executable, dlcbuilder_project, success, failure) -> bool:
        self.args = (executable, dlcbuilder_project, success, failure)
        return self.accepted


def test_discovery_prefers_explicit_environment_override(tmp_path: Path, monkeypatch) -> None:
    executable = tmp_path / "DLCBuilder.exe"
    executable.write_bytes(b"stub")
    monkeypatch.setattr("rocksmith_cdlc_generator.desktop_dlcbuilder_tools.shutil.which", lambda name: None)

    discovered = discover_dlcbuilder_executable(environ={DLCBUILDER_EXE_ENV: str(executable)})

    assert discovered == executable.resolve()


def test_discovery_falls_back_to_path(tmp_path: Path, monkeypatch) -> None:
    executable = tmp_path / "DLCBuilder.exe"
    executable.write_bytes(b"stub")
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.desktop_dlcbuilder_tools.shutil.which",
        lambda name: str(executable) if name == "DLCBuilder.exe" else None,
    )

    discovered = discover_dlcbuilder_executable(environ={})

    assert discovered == executable.resolve()


def test_require_executable_rejects_missing_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="not found"):
        require_dlcbuilder_executable(tmp_path / "missing.exe")


def test_launch_button_does_not_claim_rejected_request_started(tmp_path: Path) -> None:
    executable = tmp_path / "DLCBuilder.exe"
    executable.write_bytes(b"stub")
    request = _LaunchRequest(False)
    window = object.__new__(DlcBuilderPreparationWindow)
    window.executable_var = _Text(str(executable))
    window.launch_status_var = _Status()
    window._launch_request = request
    window._prepared_project = None

    DlcBuilderPreparationWindow._launch(window)

    assert request.args is not None
    assert request.args[0] == executable.resolve()
    assert request.args[1] is None
    assert "not started" in window.launch_status_var.value.lower()


def test_successful_preparation_is_bound_to_next_launch(tmp_path: Path) -> None:
    executable = tmp_path / "DLCBuilder.exe"
    prepared = tmp_path / "build" / "dlcbuilder" / "SecondKey.rs2dlc"
    executable.write_bytes(b"stub")
    prepared.parent.mkdir(parents=True)
    prepared.write_text("{}", encoding="utf-8")
    request = _LaunchRequest(True)
    window = object.__new__(DlcBuilderPreparationWindow)
    window.executable_var = _Text(str(executable))
    window.launch_status_var = _Status()
    window.status_var = _Status()
    window._launch_request = request
    window._prepared_project = None

    DlcBuilderPreparationWindow._succeeded(window, prepared)
    DlcBuilderPreparationWindow._launch(window)

    assert request.args is not None
    assert request.args[1] == prepared.resolve()


def test_project_switch_forgets_prepared_project(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    window = object.__new__(DlcBuilderPreparationWindow)
    window.project = first.resolve()
    window.preview_start_var = _Text("30")
    window.dlc_key_var = _Text("FirstKey")
    window.status_var = _Status()
    window.launch_status_var = _Status()
    window._prepared_project = first / "build" / "dlcbuilder" / "FirstKey.rs2dlc"

    DlcBuilderPreparationWindow.set_project(window, second)

    assert window._prepared_project is None


class _Shell:
    def __init__(self, project: Path) -> None:
        self.project = project
        self.success_callback = None
        self.failure_callback = None
        self.ui_guard = None
        self.operation = None

    def _run_background(self, label, operation, on_success, on_failure, ui_guard) -> bool:
        self.operation = operation
        self.success_callback = on_success
        self.failure_callback = on_failure
        self.ui_guard = ui_guard
        return True

    def refresh_project(self) -> None:
        pass


def test_launch_request_callbacks_are_project_bound(tmp_path: Path) -> None:
    original = tmp_path / "first"
    replacement = tmp_path / "second"
    executable = tmp_path / "DLCBuilder.exe"
    prepared = original / "build" / "dlcbuilder" / "SongKey.rs2dlc"
    original.mkdir()
    replacement.mkdir()
    executable.write_bytes(b"stub")
    shell = _Shell(original)
    successes = []
    failures = []

    accepted = ProductDesktopApp._request_dlcbuilder_launch(
        shell,
        executable,
        prepared,
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
    shell.success_callback(original / "build" / "staging" / "build_readiness.json")
    shell.failure_callback(ValueError("late launch failure"))

    assert successes == []
    assert failures == []


def test_launch_request_passes_prepared_project_to_engine(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    executable = tmp_path / "DLCBuilder.exe"
    prepared = project / "build" / "dlcbuilder" / "SecondKey.rs2dlc"
    readiness = project / "build" / "staging" / "build_readiness.json"
    project.mkdir()
    executable.write_bytes(b"stub")
    shell = _Shell(project)
    captured = {}

    def fake_launch(project_dir, *, executable, dlcbuilder_project=None):
        captured["project"] = project_dir
        captured["executable"] = executable
        captured["dlcbuilder_project"] = dlcbuilder_project
        return readiness

    monkeypatch.setattr("rocksmith_cdlc_generator.desktop_shell.launch_dlcbuilder", fake_launch)

    accepted = ProductDesktopApp._request_dlcbuilder_launch(
        shell,
        executable,
        prepared,
        lambda result: None,
        lambda error: None,
    )

    assert accepted is True
    assert shell.operation is not None
    assert shell.operation() == readiness
    assert captured == {
        "project": project,
        "executable": executable,
        "dlcbuilder_project": prepared,
    }
