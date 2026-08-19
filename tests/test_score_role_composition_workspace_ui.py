from __future__ import annotations

from pathlib import Path

from rocksmith_cdlc_generator.audio_output_ui import AudioOutputSongWorkspaceWindow
from rocksmith_cdlc_generator.score_role_composition_workspace_controls import (
    ScoreRoleCompositionTrackOption,
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


class _Combobox:
    def __init__(self) -> None:
        self.values: list[str] = []

    def configure(self, **kwargs) -> None:
        if "values" in kwargs:
            self.values = list(kwargs["values"])


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
        self.score_composition_add_var = _Var()
        self.score_composition_add_combo = _Combobox()
        self.add_score_composition_track_button = _Button()
        self.score_composition_remove_var = _Var()
        self.score_composition_remove_combo = _Combobox()
        self.remove_score_composition_track_button = _Button()


def _controls(
    *,
    enabled: bool,
    blocker: str | None = None,
    selected_track_indices: list[int] | None = None,
    selected_track_names: list[str | None] | None = None,
    available_tracks: list[ScoreRoleCompositionTrackOption] | None = None,
    removable_track_indices: list[int] | None = None,
    add_track_enabled: bool = False,
) -> ScoreRoleCompositionWorkspaceControls:
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
                selected_track_indices=selected_track_indices or [1, 3],
                selected_track_names=selected_track_names or ["Rhythm 1", "Rhythm 2"],
                available_tracks=available_tracks or [],
                removable_track_indices=removable_track_indices or [],
                add_track_enabled=add_track_enabled,
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


def test_panel_populates_add_and_remove_pickers(monkeypatch) -> None:
    harness = _Harness()
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.score_role_composition_workspace_ui."
        "build_score_role_composition_workspace_controls",
        lambda _project: _controls(
            enabled=True,
            selected_track_indices=[1, 3],
            selected_track_names=["Rhythm 1", "Rhythm 2"],
            available_tracks=[
                ScoreRoleCompositionTrackOption(source_track_index=0, name="Lead", label="Lead (track 0)")
            ],
            removable_track_indices=[3],
            add_track_enabled=True,
        ),
    )

    harness._refresh_score_composition_panel()

    assert harness.score_composition_add_combo.values == ["Lead (track 0)"]
    assert harness.add_score_composition_track_button.options["state"] == "normal"
    assert harness.score_composition_remove_combo.values == ["Rhythm 2 (track 3)"]
    assert harness.remove_score_composition_track_button.options["state"] == "normal"


def test_panel_disables_pickers_when_nothing_available_or_removable(monkeypatch) -> None:
    harness = _Harness()
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.score_role_composition_workspace_ui."
        "build_score_role_composition_workspace_controls",
        lambda _project: _controls(enabled=False, selected_track_indices=[1], selected_track_names=["Rhythm 1"]),
    )

    harness._refresh_score_composition_panel()

    assert harness.score_composition_add_combo.values == []
    assert harness.add_score_composition_track_button.options["state"] == "disabled"
    assert harness.score_composition_remove_combo.values == []
    assert harness.remove_score_composition_track_button.options["state"] == "disabled"


def test_add_track_action_calls_controller_and_refreshes(monkeypatch) -> None:
    harness = _Harness()
    harness.score_composition_add_var.set("Lead (track 0)")
    harness._score_composition_add_options = {"Lead (track 0)": 0}
    calls: list[tuple[str, int]] = []

    monkeypatch.setattr(
        "rocksmith_cdlc_generator.score_role_composition_workspace_ui.add_score_composition_track",
        lambda _project, *, arrangement, track_index: calls.append((arrangement, track_index)),
    )

    refreshed: list[bool] = []
    harness.refresh = lambda: refreshed.append(True)  # type: ignore[method-assign]

    harness._add_score_composition_track()

    assert calls == [("rhythm", 0)]
    assert refreshed == [True]


def test_add_track_action_shows_error_on_failure(monkeypatch) -> None:
    harness = _Harness()
    harness.score_composition_add_var.set("Lead (track 0)")
    harness._score_composition_add_options = {"Lead (track 0)": 0}

    def _raise(_project, *, arrangement, track_index):
        raise ValueError("track already selected")

    monkeypatch.setattr(
        "rocksmith_cdlc_generator.score_role_composition_workspace_ui.add_score_composition_track",
        _raise,
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.score_role_composition_workspace_ui."
        "build_score_role_composition_workspace_controls",
        lambda _project: _controls(enabled=False),
    )
    errors: list[str] = []
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.score_role_composition_workspace_ui.messagebox.showerror",
        lambda _title, message, parent=None: errors.append(message),
    )

    harness._add_score_composition_track()

    assert errors == ["track already selected"]


def test_remove_track_action_calls_controller_and_refreshes(monkeypatch) -> None:
    harness = _Harness()
    harness.score_composition_remove_var.set("Rhythm 2 (track 3)")
    harness._score_composition_remove_options = {"Rhythm 2 (track 3)": 3}
    calls: list[tuple[str, int]] = []

    monkeypatch.setattr(
        "rocksmith_cdlc_generator.score_role_composition_workspace_ui.remove_score_composition_track",
        lambda _project, *, arrangement, track_index: calls.append((arrangement, track_index)),
    )

    refreshed: list[bool] = []
    harness.refresh = lambda: refreshed.append(True)  # type: ignore[method-assign]

    harness._remove_score_composition_track()

    assert calls == [("rhythm", 3)]
    assert refreshed == [True]


def test_remove_track_action_shows_error_on_failure(monkeypatch) -> None:
    harness = _Harness()
    harness.score_composition_remove_var.set("Rhythm 2 (track 3)")
    harness._score_composition_remove_options = {"Rhythm 2 (track 3)": 3}

    def _raise(_project, *, arrangement, track_index):
        raise ValueError("cannot remove primary track")

    monkeypatch.setattr(
        "rocksmith_cdlc_generator.score_role_composition_workspace_ui.remove_score_composition_track",
        _raise,
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.score_role_composition_workspace_ui."
        "build_score_role_composition_workspace_controls",
        lambda _project: _controls(enabled=False),
    )
    errors: list[str] = []
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.score_role_composition_workspace_ui.messagebox.showerror",
        lambda _title, message, parent=None: errors.append(message),
    )

    harness._remove_score_composition_track()

    assert errors == ["cannot remove primary track"]
