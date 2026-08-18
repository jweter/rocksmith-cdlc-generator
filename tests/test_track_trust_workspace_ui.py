from __future__ import annotations

from pathlib import Path

from rocksmith_cdlc_generator.audio_output_ui import AudioOutputSongWorkspaceWindow
from rocksmith_cdlc_generator.track_trust_workspace_controls import (
    TrackTrustWorkspaceControl,
    TrackTrustWorkspaceControls,
)
from rocksmith_cdlc_generator.track_trust_workspace_ui import TrackTrustWorkspaceMixin


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


class _Harness(TrackTrustWorkspaceMixin):
    def __init__(self) -> None:
        self.project = Path("song")
        self.fretboard_role_var = _Var("lead")
        self.track_trust_status_var = _Var()
        self.track_trust_blocker_var = _Var()
        self.accept_track_trust_button = _Button()


def _controls(*, enabled: bool, blocker: str | None = None) -> TrackTrustWorkspaceControls:
    return TrackTrustWorkspaceControls(
        controls=[
            TrackTrustWorkspaceControl(
                arrangement="lead",
                source_track_index=2,
                source_track_name="Lead Guitar",
                note_count=731,
                review_state="unreviewed",
                button_text="Accept Track Source",
                button_enabled=enabled,
                status_text="Lead source trust has not been explicitly accepted.",
                blocker_text=blocker,
            )
        ]
    )


def test_final_song_workspace_includes_track_trust_mixin() -> None:
    assert TrackTrustWorkspaceMixin in AudioOutputSongWorkspaceWindow.__mro__


def test_panel_projects_enabled_controller_state(monkeypatch) -> None:
    harness = _Harness()
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.track_trust_workspace_ui.build_track_trust_workspace_controls",
        lambda _project: _controls(enabled=True),
    )

    harness._refresh_track_trust_panel()

    assert "Lead Guitar" in harness.track_trust_status_var.get()
    assert "731 notes" in harness.track_trust_status_var.get()
    assert harness.track_trust_blocker_var.get() == ""
    assert harness.accept_track_trust_button.options == {
        "text": "Accept Track Source",
        "state": "normal",
    }


def test_panel_keeps_blocked_track_disabled(monkeypatch) -> None:
    harness = _Harness()
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.track_trust_workspace_ui.build_track_trust_workspace_controls",
        lambda _project: _controls(
            enabled=False,
            blocker="event 12 has no explicit string/fret position",
        ),
    )

    harness._refresh_track_trust_panel()

    assert "event 12" in harness.track_trust_blocker_var.get()
    assert harness.accept_track_trust_button.options["state"] == "disabled"


def test_panel_fails_closed_when_status_cannot_be_loaded(monkeypatch) -> None:
    harness = _Harness()

    def _raise(_project):
        raise ValueError("stale fan-out")

    monkeypatch.setattr(
        "rocksmith_cdlc_generator.track_trust_workspace_ui.build_track_trust_workspace_controls",
        _raise,
    )

    harness._refresh_track_trust_panel()

    assert "stale fan-out" in harness.track_trust_status_var.get()
    assert harness.accept_track_trust_button.options["state"] == "disabled"
