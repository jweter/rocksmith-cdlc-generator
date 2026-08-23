from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from rocksmith_cdlc_generator import diagnostic_guided_desktop
from rocksmith_cdlc_generator.desktop_diagnostics import (
    diagnostic_level,
    format_diagnostic_line,
    persist_project_diagnostic,
    read_recent_project_diagnostics,
)
from rocksmith_cdlc_generator.diagnostic_guided_desktop import (
    LiveDiagnosticsGuidedDesktopApp,
    workflow_diagnostic_key,
)


def test_diagnostic_lines_are_timestamped_and_classified() -> None:
    timestamp = datetime(2026, 8, 16, 17, 45, 12, tzinfo=timezone.utc)

    assert format_diagnostic_line("Task progress: chunk 2 of 9", timestamp=timestamp) == (
        "[17:45:12] INFO    Task progress: chunk 2 of 9"
    )
    assert diagnostic_level("WARNING: heartbeat is stale") == "WARNING"
    assert diagnostic_level("ERROR: worker failed") == "ERROR"


def test_project_diagnostics_persist_as_media_free_jsonl(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    timestamp = datetime(2026, 8, 16, 17, 45, 12, tzinfo=timezone.utc)

    persist_project_diagnostic(project, "Task progress: Pitch analysis chunk 2 of 9 (22%)", timestamp=timestamp)

    path = project / "review" / "desktop_diagnostics.jsonl"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload == {
        "schema_version": 1,
        "timestamp": "2026-08-16T17:45:12+00:00",
        "level": "INFO",
        "message": "Task progress: Pitch analysis chunk 2 of 9 (22%)",
    }
    assert "audio" not in payload
    assert "score" not in payload


def test_recent_project_diagnostics_returns_tail_only(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    for index in range(12):
        persist_project_diagnostic(project, f"event {index}")

    recent = read_recent_project_diagnostics(project, limit=3)

    assert len(recent) == 3
    assert recent[0].endswith("event 9")
    assert recent[-1].endswith("event 11")


def test_persisted_utc_timestamp_is_rendered_in_local_timezone(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    timestamp = datetime(2026, 8, 16, 17, 45, 12, tzinfo=timezone.utc)
    persist_project_diagnostic(project, "local clock check", timestamp=timestamp)

    central = timezone(timedelta(hours=-5))
    recent = read_recent_project_diagnostics(project, local_timezone=central)

    assert recent == ["[12:45:12] INFO    local clock check"]


def test_boundary_timestamp_overflow_does_not_break_recent_diagnostics(tmp_path: Path) -> None:
    project = tmp_path / "song"
    review = project / "review"
    review.mkdir(parents=True)
    payload = {
        "schema_version": 1,
        "timestamp": "0001-01-01T00:00:00+00:00",
        "level": "INFO",
        "message": "boundary timestamp",
    }
    (review / "desktop_diagnostics.jsonl").write_text(json.dumps(payload) + "\n", encoding="utf-8")

    western = timezone(timedelta(hours=-5))
    recent = read_recent_project_diagnostics(project, local_timezone=western)

    assert recent == ["[--:--:--] INFO    boundary timestamp"]


def test_diagnostic_persistence_is_best_effort(tmp_path: Path) -> None:
    not_a_project_directory = tmp_path / "blocked"
    not_a_project_directory.write_text("file", encoding="utf-8")

    persist_project_diagnostic(not_a_project_directory, "must not escape as an exception")


def test_failed_same_project_reload_reports_false_instead_of_using_stale_path(monkeypatch, tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    (project / "project.json").write_text("{}", encoding="utf-8")
    errors: list[str] = []
    monkeypatch.setattr(
        diagnostic_guided_desktop.messagebox,
        "showerror",
        lambda _title, message, **_kwargs: errors.append(message),
    )
    window = SimpleNamespace(
        project=project,
        _last_workflow_diagnostic="existing-state",
        _diagnostic_project_load_in_progress=False,
    )

    loaded = LiveDiagnosticsGuidedDesktopApp.load_project(window, project)

    assert loaded is False
    assert window.project == project
    assert window._last_workflow_diagnostic == "existing-state"
    assert window._diagnostic_project_load_in_progress is False
    assert errors and "Could not open project" in errors[0]


def test_workflow_deduplication_key_is_scoped_to_project(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    first_key = workflow_diagnostic_key(first, "47% prepared", "Review timing")
    second_key = workflow_diagnostic_key(second, "47% prepared", "Review timing")

    assert first_key != second_key


def test_live_diagnostics_desktop_subclasses_guided_product_shell() -> None:
    from rocksmith_cdlc_generator.guided_desktop import GuidedDesktopApp

    assert issubclass(LiveDiagnosticsGuidedDesktopApp, GuidedDesktopApp)


def test_successful_project_load_refreshes_workspace_state_exactly_once(
    monkeypatch, tmp_path: Path
) -> None:
    """#304/#193: load_project must not re-run the whole refresh cascade twice.

    The base DesktopApp.load_project (and every other shell's load_project)
    calls refresh_project() exactly once per project open. Before this fix,
    LiveDiagnosticsGuidedDesktopApp.load_project called it a second time --
    re-running workflow-plan recomputation and every open window's refresh --
    solely to log one "Workflow state: ..." diagnostic line. That line is now
    produced by a dedicated, cheap helper instead of a second full refresh.
    """

    project = tmp_path / "song"
    project.mkdir()
    manifest = SimpleNamespace(project_name="My Song")
    monkeypatch.setattr(
        diagnostic_guided_desktop.ProjectManifest,
        "load",
        lambda _project_dir: manifest,
    )

    refresh_calls: list[None] = []
    logged: list[str] = []
    window = SimpleNamespace(
        project=None,
        project_var=SimpleNamespace(set=lambda _value: None),
        song_var=SimpleNamespace(set=lambda _value: None),
        _remember_project=lambda _project: None,
        _log=lambda message: logged.append(message),
        refresh_project=lambda: refresh_calls.append(None),
        _render_persisted_diagnostics=lambda: None,
        _log_workflow_state_if_changed=lambda: logged.append("Workflow state: stub"),
        _last_workflow_diagnostic="stale",
        _diagnostic_project_load_in_progress=False,
    )

    loaded = LiveDiagnosticsGuidedDesktopApp.load_project(window, project)

    assert loaded is True
    assert len(refresh_calls) == 1
    assert logged == [
        f"Opened project: {project}",
        "Project opened: song",
        "Workflow state: stub",
    ]
