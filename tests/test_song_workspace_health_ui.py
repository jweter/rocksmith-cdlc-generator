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


class _Tree:
    def __init__(self) -> None:
        self.rows = ["stale-row"]

    def get_children(self) -> tuple[str, ...]:
        return tuple(self.rows)

    def delete(self, *rows: str) -> None:
        self.rows = [row for row in self.rows if row not in rows]


class _Notebook:
    def __init__(self, tabs: list[object]) -> None:
        self.tabs = tabs
        self.states = ["normal"] * len(tabs)
        self.selected: object | None = None

    def index(self, target: object) -> int:
        if target == "end":
            return len(self.tabs)
        return self.tabs.index(target)

    def select(self, tab: object) -> None:
        self.selected = tab

    def tab(self, index: int, *, state: str) -> None:
        self.states[index] = state


class _Canvas:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def delete(self, target: str) -> None:
        self.deleted.append(target)


def _snapshot(health: str) -> SimpleNamespace:
    return SimpleNamespace(health=health, progress_percent=42)


def _window() -> SimpleNamespace:
    overview_tab = object()
    notebook = _Notebook([overview_tab, object(), object(), object()])
    return SimpleNamespace(
        project=object(),
        snapshot=object(),
        notebook=notebook,
        overview_tab=overview_tab,
        _selected_time=12.0,
        song_var=_Var("Stale song"),
        health_var=_Var(),
        health_label=_Widget(),
        progress_var=_Var(),
        progress=_Widget(),
        progress_text_var=_Var(),
        next_action_var=_Var("Stale action"),
        overview_vars={
            "recording": _Var("Stale recording"),
            "score": _Var("Stale score"),
            "timeline": _Var("Stale timeline"),
            "review": _Var("Stale review"),
        },
        overview_tree=_Tree(),
        arrangement_tree=_Tree(),
        review_tree=_Tree(),
        review_detail_var=_Var("Stale review detail"),
        timeline_summary_var=_Var("Stale timeline summary"),
        timeline_cursor_var=_Var("Cursor: 00:12"),
        recording_detail_var=_Var("C:\\Users\\Jeremy\\private.wav"),
        recording_rights_status_var=_Var("✓ PASS"),
        recording_rights_status_label=_Widget(),
        score_detail_var=_Var("private.gp5"),
        score_rights_status_var=_Var("✓ PASS"),
        score_rights_status_label=_Widget(),
        timeline_canvas=_Canvas(),
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


def test_refresh_failure_fails_closed_sanitizes_details_and_offers_recovery(monkeypatch) -> None:
    window = _window()

    def show_refresh_failure(exc: Exception) -> None:
        SongWorkspaceWindow._show_refresh_failure(window, exc)

    window._show_refresh_failure = show_refresh_failure
    window.health_label.configured["foreground"] = "#55D98D"
    window.progress_var.set(100)
    window.progress.configured["style"] = "Status.Pass.Horizontal.TProgressbar"

    private_error = r"C:\Users\Jeremy\private-project\score.gp5 became unreadable"

    def fail_snapshot(_project):
        raise ValueError(private_error)

    monkeypatch.setattr(song_workspace_ui, "build_song_workspace_snapshot", fail_snapshot)

    SongWorkspaceWindow.refresh(window)

    assert window.snapshot is None
    assert window._selected_time is None
    assert window.song_var.value == "Song Workspace unavailable"
    assert window.health_var.value == (
        "Project health: ✗ FAIL — Workspace refresh unavailable (ValueError)"
    )
    assert private_error not in window.health_var.value
    assert "Jeremy" not in window.health_var.value
    assert "score.gp5" not in window.health_var.value
    assert window.health_label.configured["foreground"] == "#FF746C"
    assert window.progress_var.value == 0
    assert window.progress.configured["style"] == "Status.Fail.Horizontal.TProgressbar"
    assert window.progress_text_var.value == "Refresh failed · progress unavailable"
    assert window.next_action_var.value.startswith("Refresh the workspace to retry")
    assert all(
        value.value == "Unavailable — workspace refresh failed"
        for value in window.overview_vars.values()
    )
    assert window.overview_tree.rows == []
    assert window.arrangement_tree.rows == []
    assert window.review_tree.rows == []
    assert "were not changed" in window.review_detail_var.value
    assert window.recording_detail_var.value == ""
    assert window.score_detail_var.value == ""
    assert window.recording_rights_status_var.value == "✗ FAIL — unavailable"
    assert window.score_rights_status_var.value == "✗ FAIL — unavailable"
    assert window.timeline_canvas.deleted == ["all"]
    assert window.notebook.selected is window.overview_tab
    assert window.notebook.states == ["normal", "disabled", "disabled", "disabled"]

    SongWorkspaceWindow._set_refresh_surface_available(window, True)

    assert window.notebook.states == ["normal", "normal", "normal", "normal"]
