from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import rocksmith_cdlc_generator.song_workspace_ui as song_workspace_ui
from rocksmith_cdlc_generator.song_workspace_ui import SongWorkspaceWindow


class _Button:
    def __init__(self) -> None:
        self.options: dict[str, object] = {}

    def configure(self, **kwargs: object) -> None:
        self.options.update(kwargs)


def _snapshot(next_step_id: str | None) -> SimpleNamespace:
    return SimpleNamespace(next_step_id=next_step_id)


def _candidate(**overrides: object) -> SimpleNamespace:
    values = dict(
        authority_role=SimpleNamespace(value="bass"),
        authority_track_index=2,
        method="beat-grid-piecewise-linear-v1",
        confidence=0.94,
        global_offset_seconds=0.125,
        warnings=[],
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_promote_button_enabled_only_for_active_shared_timeline_gate() -> None:
    window = SimpleNamespace(promote_shared_timeline_button=_Button())

    SongWorkspaceWindow._refresh_promote_shared_timeline_action(window, _snapshot("shared-timeline"))
    assert window.promote_shared_timeline_button.options["state"] == "normal"

    SongWorkspaceWindow._refresh_promote_shared_timeline_action(window, _snapshot("align-tab"))
    assert window.promote_shared_timeline_button.options["state"] == "disabled"

    SongWorkspaceWindow._refresh_promote_shared_timeline_action(window, _snapshot(None))
    assert window.promote_shared_timeline_button.options["state"] == "disabled"


def test_promote_from_next_action_confirms_and_promotes_reviewed_candidate(monkeypatch, tmp_path: Path) -> None:
    candidate = _candidate()
    confirmations: list[str] = []
    called: dict[str, object] = {}
    refreshed: list[bool] = []

    monkeypatch.setattr(song_workspace_ui, "build_shared_timeline_candidate", lambda _project: candidate)

    def fake_askyesno(_title: str, message: str, **_kwargs: object) -> bool:
        confirmations.append(message)
        return True

    monkeypatch.setattr(song_workspace_ui.messagebox, "askyesno", fake_askyesno)

    def fake_promote(project: Path, *, expected_candidate=None) -> Path:
        called["project"] = project
        called["expected_candidate"] = expected_candidate
        return project / "analysis" / "shared_timeline.json"

    monkeypatch.setattr(song_workspace_ui, "promote_shared_timeline", fake_promote)

    window = SimpleNamespace(project=tmp_path, refresh=lambda: refreshed.append(True))

    SongWorkspaceWindow._promote_shared_timeline_from_next_action(window)

    assert called == {"project": tmp_path, "expected_candidate": candidate}
    assert refreshed == [True]
    assert confirmations and "Bass track 2" in confirmations[0]
    assert "0.94" in confirmations[0]


def test_promote_from_next_action_warns_when_not_ready(monkeypatch, tmp_path: Path) -> None:
    warned: list[str] = []

    def fake_build(_project: Path):
        raise ValueError("current alignment track does not match the confirmed Bass mapping")

    monkeypatch.setattr(song_workspace_ui, "build_shared_timeline_candidate", fake_build)
    monkeypatch.setattr(
        song_workspace_ui.messagebox,
        "showwarning",
        lambda _title, message, **_kwargs: warned.append(message),
    )
    monkeypatch.setattr(
        song_workspace_ui,
        "promote_shared_timeline",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not promote an unready candidate")),
    )

    window = SimpleNamespace(project=tmp_path)

    SongWorkspaceWindow._promote_shared_timeline_from_next_action(window)

    assert warned and "current alignment track does not match" in warned[0]


def test_promote_from_next_action_declines_without_confirmation(monkeypatch, tmp_path: Path) -> None:
    candidate = _candidate()
    monkeypatch.setattr(song_workspace_ui, "build_shared_timeline_candidate", lambda _project: candidate)
    monkeypatch.setattr(song_workspace_ui.messagebox, "askyesno", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        song_workspace_ui,
        "promote_shared_timeline",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not promote without confirmation")),
    )

    window = SimpleNamespace(project=tmp_path)

    SongWorkspaceWindow._promote_shared_timeline_from_next_action(window)


def test_promote_from_next_action_surfaces_stale_candidate_error_without_refresh(monkeypatch, tmp_path: Path) -> None:
    candidate = _candidate()
    errored: list[str] = []
    refreshed: list[bool] = []

    monkeypatch.setattr(song_workspace_ui, "build_shared_timeline_candidate", lambda _project: candidate)
    monkeypatch.setattr(song_workspace_ui.messagebox, "askyesno", lambda *_args, **_kwargs: True)

    def fake_promote(_project: Path, *, expected_candidate=None) -> Path:
        raise ValueError("shared timing candidate changed after review; refresh Song Workspace")

    monkeypatch.setattr(song_workspace_ui, "promote_shared_timeline", fake_promote)
    monkeypatch.setattr(
        song_workspace_ui.messagebox,
        "showerror",
        lambda _title, message, **_kwargs: errored.append(message),
    )

    window = SimpleNamespace(project=tmp_path, refresh=lambda: refreshed.append(True))

    SongWorkspaceWindow._promote_shared_timeline_from_next_action(window)

    assert errored and "changed after review" in errored[0]
    assert refreshed == []
