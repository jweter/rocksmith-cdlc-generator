from __future__ import annotations

from types import SimpleNamespace

import rocksmith_cdlc_generator.song_workspace_ui as song_workspace_ui
from rocksmith_cdlc_generator.song_workspace_ui import SongWorkspaceWindow


class _Var:
    def __init__(self, value: object = "") -> None:
        self.value = value

    def set(self, value: object) -> None:
        self.value = value


class _Widget:
    """Minimal stand-in for a ttk widget covering only ``.configure(...)`` calls."""

    def __init__(self) -> None:
        self.configured: dict[str, object] = {}

    def configure(self, **kwargs: object) -> None:
        self.configured.update(kwargs)


def _snapshot(health: str) -> SimpleNamespace:
    return SimpleNamespace(health=health, progress_percent=42)


def _window() -> SimpleNamespace:
    return SimpleNamespace(
        project=object(),
        snapshot=object(),
        health_var=_Var(),
        health_label=_Widget(),
        progress_var=_Var(),
        progress=_Widget(),
        progress_text_var=_Var(),
    )


def test_blocked_health_renders_non_color_alone_fail_status_and_colors_the_bar() -> None:
    """#305: health status uses the packaged app's dark-theme semantic palette."""

    window = _window()

    SongWorkspaceWindow._refresh_health_indicator(window, _snapshot("BLOCKED"))

    assert window.health_var.value == "Project health: ✗ FAIL — Blocked — validation problems must be resolved"
    assert window.health_label.configured["foreground"] == "#FF746C"
    assert window.progress.configured["style"] == "Status.Fail.Horizontal.TProgressbar"
    assert window.progress_var.value == 42


def test_ready_health_renders_pass_status() -> None:
    window = _window()

    SongWorkspaceWindow._refresh_health_indicator(window, _snapshot("READY"))

    assert window.health_var.value.startswith("Project health: ✓ PASS")
    assert window.health_label.configured["foreground"] == "#55D98D"
    assert window.progress.configured["style"] == "Status.Pass.Horizontal.TProgressbar"


def test_review_health_renders_review_required_status() -> None:
    window = _window()

    SongWorkspaceWindow._refresh_health_indicator(window, _snapshot("REVIEW"))

    assert window.health_var.value.startswith("Project health: ◉ REVIEW REQUIRED")
    assert window.health_label.configured["foreground"] == "#8F82F5"
    assert window.progress.configured["style"] == "Status.ReviewRequired.Horizontal.TProgressbar"


def test_new_and_in_progress_both_render_info_status_but_distinct_text() -> None:
    new_window = _window()
    in_progress_window = _window()

    SongWorkspaceWindow._refresh_health_indicator(new_window, _snapshot("NEW"))
    SongWorkspaceWindow._refresh_health_indicator(in_progress_window, _snapshot("IN_PROGRESS"))

    assert new_window.health_var.value.startswith("Project health: ℹ INFO")
    assert in_progress_window.health_var.value.startswith("Project health: ℹ INFO")
    assert new_window.health_var.value != in_progress_window.health_var.value
    assert new_window.health_label.configured["foreground"] == "#B7C4D6"
    assert new_window.progress.configured["style"] == "Status.Info.Horizontal.TProgressbar"


def test_refresh_failure_clears_stale_ready_progress_and_uses_failure_styling(monkeypatch) -> None:
    window = _window()
    window.health_label.configured["foreground"] = "#55D98D"
    window.progress_var.set(100)
    window.progress.configured["style"] = "Status.Pass.Horizontal.TProgressbar"

    def fail_snapshot(_project):
        raise ValueError("project became unreadable")

    monkeypatch.setattr(song_workspace_ui, "build_song_workspace_snapshot", fail_snapshot)

    SongWorkspaceWindow.refresh(window)

    assert window.snapshot is None
    assert window.health_var.value == "Could not refresh: project became unreadable"
    assert window.health_label.configured["foreground"] == "#FF746C"
    assert window.progress_var.value == 0
    assert window.progress.configured["style"] == "Status.Fail.Horizontal.TProgressbar"
    assert window.progress_text_var.value == "Refresh failed · progress unavailable"
