from __future__ import annotations

from types import SimpleNamespace

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
        health_var=_Var(),
        health_label=_Widget(),
        progress_var=_Var(),
        progress=_Widget(),
    )


def test_blocked_health_renders_non_color_alone_fail_status_and_colors_the_bar() -> None:
    """#305: the Song Workspace header previously rendered ``snapshot.health`` as a
    raw ``WorkspaceHealth`` string ("BLOCKED"/"READY"/...) with no color, symbol, or
    weight differentiation, and the progress bar rendered identically regardless of
    health (desktop-ui-audit.md finding #2, "progress indicators" in the #305 "Areas
    to review" list). The header should now carry the shared symbol+label semantic
    status text and a matching progress-bar fill style.
    """

    window = _window()

    SongWorkspaceWindow._refresh_health_indicator(window, _snapshot("BLOCKED"))

    assert window.health_var.value == "Project health: ✗ FAIL — Blocked — validation problems must be resolved"
    assert window.health_label.configured["foreground"] == "#B3261E"
    assert window.progress.configured["style"] == "Status.Fail.Horizontal.TProgressbar"
    assert window.progress_var.value == 42


def test_ready_health_renders_pass_status() -> None:
    window = _window()

    SongWorkspaceWindow._refresh_health_indicator(window, _snapshot("READY"))

    assert window.health_var.value.startswith("Project health: ✓ PASS")
    assert window.health_label.configured["foreground"] == "#1B5E20"
    assert window.progress.configured["style"] == "Status.Pass.Horizontal.TProgressbar"


def test_review_health_renders_review_required_status() -> None:
    window = _window()

    SongWorkspaceWindow._refresh_health_indicator(window, _snapshot("REVIEW"))

    assert window.health_var.value.startswith("Project health: ◉ REVIEW REQUIRED")
    assert window.health_label.configured["foreground"] == "#3F51B5"
    assert window.progress.configured["style"] == "Status.ReviewRequired.Horizontal.TProgressbar"


def test_new_and_in_progress_both_render_info_status_but_distinct_text() -> None:
    new_window = _window()
    in_progress_window = _window()

    SongWorkspaceWindow._refresh_health_indicator(new_window, _snapshot("NEW"))
    SongWorkspaceWindow._refresh_health_indicator(in_progress_window, _snapshot("IN_PROGRESS"))

    assert new_window.health_var.value.startswith("Project health: ℹ INFO")
    assert in_progress_window.health_var.value.startswith("Project health: ℹ INFO")
    assert new_window.health_var.value != in_progress_window.health_var.value
    assert new_window.health_label.configured["foreground"] == "#37474F"
    assert new_window.progress.configured["style"] == "Status.Info.Horizontal.TProgressbar"
