import json
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


def test_window_success_status_names_reviewed_score_anchor_timing(tmp_path: Path) -> None:
    manifest_path = tmp_path / "export_manifest.json"
    manifest_path.write_text(json.dumps({"timing_source": "reviewed_score_anchors"}), encoding="utf-8")
    xml_path = tmp_path / "arr_bass_RS2.xml"
    window = object.__new__(RocksmithXmlExportWindow)
    window.status_vars = {"bass": _Status()}

    RocksmithXmlExportWindow._succeeded(window, "bass", {"xml": xml_path, "manifest": manifest_path})

    status = window.status_vars["bass"].value
    assert "reviewed score-anchor timing" in status
    assert str(xml_path) in status


def test_window_success_status_names_legacy_chart_timing(tmp_path: Path) -> None:
    manifest_path = tmp_path / "export_manifest.json"
    manifest_path.write_text(json.dumps({"timing_source": "legacy_chart"}), encoding="utf-8")
    xml_path = tmp_path / "arr_lead_RS2.xml"
    window = object.__new__(RocksmithXmlExportWindow)
    window.status_vars = {"lead": _Status()}

    RocksmithXmlExportWindow._succeeded(window, "lead", {"xml": xml_path, "manifest": manifest_path})

    status = window.status_vars["lead"].value
    assert "legacy chart timing" in status
    assert str(xml_path) in status


def test_window_success_status_degrades_gracefully_without_manifest() -> None:
    xml_path = Path("arr_rhythm_RS2.xml")
    window = object.__new__(RocksmithXmlExportWindow)
    window.status_vars = {"rhythm": _Status()}

    RocksmithXmlExportWindow._succeeded(window, "rhythm", {"xml": xml_path})

    assert window.status_vars["rhythm"].value == f"Exported: {xml_path}"


def test_window_success_status_degrades_gracefully_on_unreadable_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "missing_export_manifest.json"
    xml_path = tmp_path / "arr_bass_RS2.xml"
    window = object.__new__(RocksmithXmlExportWindow)
    window.status_vars = {"bass": _Status()}

    RocksmithXmlExportWindow._succeeded(window, "bass", {"xml": xml_path, "manifest": manifest_path})

    assert window.status_vars["bass"].value == f"Exported: {xml_path}"


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
        self.ui_guard = None
        self.refreshes = 0

    def _run_background(
        self,
        label,
        operation,
        on_success,
        on_failure,
        ui_guard=None,
    ) -> bool:
        self.success_callback = on_success
        self.failure_callback = on_failure
        self.ui_guard = ui_guard
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
    assert shell.ui_guard is not None

    shell.project = replacement
    assert shell.ui_guard() is False
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
    assert shell.ui_guard is not None
    assert shell.ui_guard() is True
    error = ValueError("validation blocked")
    shell.failure_callback(error)

    assert failures == [error]


class _CompletionHarness:
    def __init__(self) -> None:
        self.busy_updates = []
        self.generic_failures = []
        self.generic_successes = []

    def _set_busy(self, busy: bool, message=None) -> None:
        self.busy_updates.append((busy, message))

    def _background_failed(self, error: Exception, traceback_text: str) -> None:
        self.generic_failures.append((error, traceback_text))

    def _background_succeeded(self, result, on_success) -> None:
        self.generic_successes.append((result, on_success))


def test_stale_failure_suppresses_generic_project_ui_handling() -> None:
    harness = _CompletionHarness()
    callbacks = []
    error = ValueError("old project failed")

    ProductDesktopApp._finish_background_failure(
        harness,
        error,
        "traceback",
        callbacks.append,
        lambda: False,
    )

    assert harness.busy_updates == [(False, None)]
    assert harness.generic_failures == []
    assert callbacks == []


def test_stale_success_suppresses_generic_project_ui_handling() -> None:
    harness = _CompletionHarness()
    callbacks = []

    ProductDesktopApp._finish_background_success(
        harness,
        {"xml": Path("old.xml")},
        callbacks.append,
        lambda: False,
    )

    assert harness.busy_updates == [(False, None)]
    assert harness.generic_successes == []
    assert callbacks == []


def test_current_failure_keeps_generic_and_arrangement_reporting() -> None:
    harness = _CompletionHarness()
    callbacks = []
    error = ValueError("current project failed")

    ProductDesktopApp._finish_background_failure(
        harness,
        error,
        "traceback",
        callbacks.append,
        lambda: True,
    )

    assert harness.busy_updates == []
    assert harness.generic_failures == [(error, "traceback")]
    assert callbacks == [error]
