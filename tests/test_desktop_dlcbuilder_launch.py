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

    def __call__(self, executable, success, failure) -> bool:
        self.args = (executable, success, failure)
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

    DlcBuilderPreparationWindow._launch(window)

    assert request.args is not None
    assert request.args[0] == executable.resolve()
    assert "not started" in window.launch_status_var.value.lower()


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
    original.mkdir()
    replacement.mkdir()
    executable.write_bytes(b"stub")
    shell = _Shell(original)
    successes = []
    failures = []

    accepted = ProductDesktopApp._request_dlcbuilder_launch(
        shell,
        executable,
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
