from __future__ import annotations

from pathlib import Path

from rocksmith_cdlc_generator.eof_bridge import EOFBridgeError
from rocksmith_cdlc_generator.eof_workspace_ui import (
    EOFWorkspaceMixin,
    build_eof_workspace_status,
)


def test_eof_workspace_status_is_enabled_for_compatible_score_and_installed_eof(
    monkeypatch,
    tmp_path: Path,
) -> None:
    score = tmp_path / "song.gp5"
    executable = tmp_path / "eof.exe"
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.eof_workspace_ui.resolve_registered_score_for_eof",
        lambda _project: score,
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.eof_workspace_ui.discover_eof_executable",
        lambda: executable,
    )

    status = build_eof_workspace_status(tmp_path)

    assert status.available is True
    assert status.button_text == "Open in EOF"
    assert status.score_path == score
    assert status.executable == executable
    assert "does not change project authority" in status.status_text


def test_eof_workspace_status_explains_missing_optional_install(
    monkeypatch,
    tmp_path: Path,
) -> None:
    score = tmp_path / "song.gp5"
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.eof_workspace_ui.resolve_registered_score_for_eof",
        lambda _project: score,
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.eof_workspace_ui.discover_eof_executable",
        lambda: None,
    )

    status = build_eof_workspace_status(tmp_path)

    assert status.available is False
    assert status.score_path == score
    assert "ROCKSMITH_CDLC_EOF_EXE" in status.status_text


def test_eof_workspace_status_fails_closed_for_incompatible_project(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def _reject(_project: Path) -> Path:
        raise EOFBridgeError("registered score uses musicxml")

    monkeypatch.setattr(
        "rocksmith_cdlc_generator.eof_workspace_ui.resolve_registered_score_for_eof",
        _reject,
    )

    status = build_eof_workspace_status(tmp_path)

    assert status.available is False
    assert status.score_path is None
    assert "registered score uses musicxml" in status.status_text


def test_final_workspace_includes_eof_mixin() -> None:
    from rocksmith_cdlc_generator.audio_output_ui import AudioOutputSongWorkspaceWindow

    assert issubclass(AudioOutputSongWorkspaceWindow, EOFWorkspaceMixin)
