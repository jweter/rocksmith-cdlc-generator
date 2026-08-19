from __future__ import annotations

from pathlib import Path

from rocksmith_cdlc_generator.audio_output_ui import AudioOutputSongWorkspaceWindow
from rocksmith_cdlc_generator.score_role_composition_workspace_controls import (
    ScoreRoleCompositionWorkspaceControl,
    ScoreRoleCompositionWorkspaceControls,
)
from rocksmith_cdlc_generator.score_role_composition_workspace_ui import (
    ScoreRoleCompositionWorkspaceMixin,
)


class _Var:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class _Button:
    def __init__(self) -> None:
        self.options: dict[str, str] = {}

    def configure(self, **kwargs) -> None:
        self.options.update(kwargs)


class _Base:
    def refresh(self) -> None:
        pass


class _Harness(ScoreRoleCompositionWorkspaceMixin, _Base):
    def __init__(self) -> None:
        self.project = Path("song")
        self.fretboard_role_var = _Var("rhythm")
        self.score_composition_status_var = _Var()
        self.score_composition_blocker_var = _Var()
        self.compose_score_role_button = _Button()


def _controls(*, enabled: bool, blocker: str | None = None) -> ScoreRoleCompositionWorkspaceControls:
    return ScoreRoleCompositionWorkspaceControls(
        controls=[
            ScoreRoleCompositionWorkspaceControl(
                arrangement="rhythm",
                is_multi_track=True,
                state="multi_track_pending",
                overlap_count=0 if enabled else 2,
                status_text="Rhythm has 2 tracks selected (Rhythm 1, Rhythm 2) with no overlaps to resolve.",
                compose_button_text="Compose From Selected Tracks",
                compose_button_enabled=enabled,
                blocker_text=blocker,
            )
        ]
    )


def test_final_song_workspace_includes_score_composition_mixin() -> None:
    assert ScoreRoleCompositionWorkspaceMixin in AudioOutputSongWorkspaceWindow.__mro__


def test_panel_projects_enabled_controller_state(monkeypatch) -> None:
    harness = _Harness()
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.score_role_composition_workspace_ui."
        "build_score_role_composition_workspace_controls",
        lambda _project: _controls(enabled=True),
    )

    harness._refresh_score_composition_panel()

    assert "no overlaps to resolve" in harness.score_composition_status_var.get()
    assert harness.score_composition_blocker_var.get() == ""
    assert harness.compose_score_role_button.options == {
        "text": "Compose From Selected Tracks",
        "state": "normal",
    }


def test_panel_keeps_overlap_pending_role_disabled(monkeypatch) -> None:
    harness = _Harness()
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.score_role_composition_workspace_ui."
        "build_score_role_composition_workspace_controls",
        lambda _project: _controls(
            enabled=False,
            blocker="2 unresolved cross-track overlap(s); resolve via cdlc-score-composition",
        ),
    )

    harness._refresh_score_composition_panel()

    assert "cdlc-score-composition" in harness.score_composition_blocker_var.get()
    assert harness.compose_score_role_button.options["state"] == "disabled"


def test_panel_fails_closed_when_status_cannot_be_loaded(monkeypatch) -> None:
    harness = _Harness()

    def _raise(_project):
        raise ValueError("stale composition plan")

    monkeypatch.setattr(
        "rocksmith_cdlc_generator.score_role_composition_workspace_ui."
        "build_score_role_composition_workspace_controls",
        _raise,
    )

    harness._refresh_score_composition_panel()

    assert "stale composition plan" in harness.score_composition_status_var.get()
    assert harness.compose_score_role_button.options["state"] == "disabled"


def test_compose_action_refreshes_panel_on_success(monkeypatch) -> None:
    harness = _Harness()
    refreshed = _controls(enabled=False, blocker=None)

    monkeypatch.setattr(
        "rocksmith_cdlc_generator.score_role_composition_workspace_ui."
        "compose_role_composition_from_workspace",
        lambda _project, *, arrangement: refreshed,
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.score_role_composition_workspace_ui."
        "build_score_role_composition_workspace_controls",
        lambda _project: refreshed,
    )

    harness._compose_score_role_composition()

    assert "no overlaps to resolve" in harness.score_composition_status_var.get()


def test_compose_action_shows_error_and_refreshes_on_failure(monkeypatch) -> None:
    harness = _Harness()

    def _raise(_project, *, arrangement):
        raise ValueError("cannot compose rhythm from the workspace")

    monkeypatch.setattr(
        "rocksmith_cdlc_generator.score_role_composition_workspace_ui."
        "compose_role_composition_from_workspace",
        _raise,
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.score_role_composition_workspace_ui."
        "build_score_role_composition_workspace_controls",
        lambda _project: _controls(enabled=False, blocker="cannot compose"),
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.score_role_composition_workspace_ui.messagebox.showerror",
        lambda *args, **kwargs: None,
    )

    harness._compose_score_role_composition()

    assert harness.compose_score_role_button.options["state"] == "disabled"
