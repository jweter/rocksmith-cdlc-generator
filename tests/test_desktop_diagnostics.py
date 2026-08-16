from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from rocksmith_cdlc_generator.desktop_diagnostics import (
    diagnostic_level,
    format_diagnostic_line,
    persist_project_diagnostic,
    read_recent_project_diagnostics,
)
from rocksmith_cdlc_generator.diagnostic_guided_desktop import LiveDiagnosticsGuidedDesktopApp


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


def test_diagnostic_persistence_is_best_effort(tmp_path: Path) -> None:
    not_a_project_directory = tmp_path / "blocked"
    not_a_project_directory.write_text("file", encoding="utf-8")

    persist_project_diagnostic(not_a_project_directory, "must not escape as an exception")


def test_live_diagnostics_desktop_subclasses_guided_product_shell() -> None:
    from rocksmith_cdlc_generator.guided_desktop import GuidedDesktopApp

    assert issubclass(LiveDiagnosticsGuidedDesktopApp, GuidedDesktopApp)
