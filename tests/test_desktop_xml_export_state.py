from pathlib import Path

from rocksmith_cdlc_generator.desktop_shell import ProductDesktopApp
from rocksmith_cdlc_generator.desktop_xml_export_window import RocksmithXmlExportWindow


class _Status:
    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value


class _WindowRequest:
    def __init__(self, accepted: bool) -> None:
        self.accepted = accepted
        self.success = None
        self.failure = None

    def __call__(self, arrangement, success, failure) -> bool:
        self.success = success
        self.failure = failure
        return self.accepted


def test_window_does_not_mark_rejected_request_running() -> None:
    request = _WindowRequest(False)
    window = object.__new__(RocksmithXmlExportWindow)
    window.status_vars = {"bass": _Status()}
    window._export_request = request

    RocksmithXmlExportWindow._request(window, "bass")

    assert "not started" in window.status_vars["bass"].value.lower()


def test_window_reports_export_failure_after_accepted_request() -> None:
    request = _WindowRequest(True)
    window = object.__new__(RocksmithXmlExportWindow)
    window.status_vars = {"lead": _Status()}
    window._export_request = request

    RocksmithXmlExportWindow._request(window, "lead")
    assert "running" in window.status_vars["lead"].value.lower()

    assert request.failure is not None
    request.failure(ValueError("validation blocked"))
    assert "export failed" in window.status_vars["lead"].value.lower()
    assert "validation blocked" in window.status_vars["lead"].value.lower()


def test_background_runner_rejects_new_work_while_busy() -> None:
    app = object.__new__(ProductDesktopApp)
    app._busy = True

    accepted = ProductDesktopApp._run_background(app, "ignored", lambda: None)

    assert accepted is False


class _Shell:
    def __init__(self, project: Path) -> None:
        self.project = project
        self.success_callback = None
        self.failure_callback = None
        self.refreshes = 0

    def _run_background(self, label, operation, on_success, on_failure) -> bool:
        self.success_callback = on_success
        self.failure_callback = on_failure
        return True

    def refresh_song_workspace(self) -> None:
        self.refreshes += 1

    def refresh_project(self) -> None:
        self.refreshes += 1


def test_export_completion_from_previous_project_is_ignored(tmp_path: Path) -> None:
    original = tmp_path / "first"
    replacement = tmp_path / "second"
    original.mkdir()
    replacement.mkdir()
    shell = _Shell(original)
    successes = []
    failures = []

    accepted = ProductDesktopApp._request_xml_export(
        shell,
        "rhythm",
        successes.append,
        failures.append,
    )
    assert accepted is True
    assert shell.success_callback is not None
    assert shell.failure_callback is not None

    shell.project = replacement
    shell.success_callback({"xml": original / "build" / "rhythm.xml"})
    shell.failure_callback(ValueError("late failure"))

    assert successes == []
    assert failures == []
    assert shell.refreshes == 0


def test_export_failure_updates_current_project_callback(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    shell = _Shell(project)
    failures = []

    ProductDesktopApp._request_xml_export(shell, "bass", lambda outputs: None, failures.append)
    assert shell.failure_callback is not None
    error = ValueError("validation blocked")
    shell.failure_callback(error)

    assert failures == [error]
