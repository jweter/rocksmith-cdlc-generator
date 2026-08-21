from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from rocksmith_cdlc_generator.eof_bridge import EOFBridgeError
from rocksmith_cdlc_generator.eof_compatibility import EOFCompatibilityMismatch
from rocksmith_cdlc_generator.eof_workspace_ui import (
    EOFWorkspaceMixin,
    build_eof_report_workspace_status,
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


def test_eof_report_workspace_status_explains_absent_report(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.eof_workspace_ui.load_current_project_eof_compatibility_report",
        lambda _project: None,
    )

    status = build_eof_report_workspace_status(tmp_path)

    assert status.current is False
    assert "No current EOF comparison report" in status.status_text


def test_eof_report_workspace_status_surfaces_current_match_without_acceptance(
    monkeypatch,
    tmp_path: Path,
) -> None:
    report = SimpleNamespace(
        instrument="bass",
        eof_version="manual-review-pending",
        comparison=SimpleNamespace(fixture_id="synthetic-bass", mismatches=[]),
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.eof_workspace_ui.load_current_project_eof_compatibility_report",
        lambda _project: report,
    )

    status = build_eof_report_workspace_status(tmp_path)

    assert status.current is True
    assert "0 discrepancies for Bass" in status.status_text
    assert "manual-review-pending" in status.status_text
    assert "does not accept chart state" in status.status_text


def test_eof_report_workspace_status_groups_current_discrepancies(
    monkeypatch,
    tmp_path: Path,
) -> None:
    report = SimpleNamespace(
        instrument="lead",
        eof_version="1.8RC14",
        comparison=SimpleNamespace(
            fixture_id="lead-observation",
            mismatches=[
                EOFCompatibilityMismatch(
                    field="note_position", event_index=0, expected="(1, 3)", actual="(1, 4)"
                ),
                EOFCompatibilityMismatch(
                    field="note_position", event_index=1, expected="(2, 5)", actual="(2, 6)"
                ),
                EOFCompatibilityMismatch(
                    field="note_timing", event_index=1, expected="1.0/0.5", actual="1.1/0.5"
                ),
            ],
        ),
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.eof_workspace_ui.load_current_project_eof_compatibility_report",
        lambda _project: report,
    )

    status = build_eof_report_workspace_status(tmp_path)

    assert status.current is True
    assert "3 discrepancies for Lead" in status.status_text
    assert "note position: 2" in status.status_text
    assert "note timing: 1" in status.status_text
    assert "Review evidence only" in status.status_text


def test_eof_report_workspace_status_marks_stale_report(monkeypatch, tmp_path: Path) -> None:
    def _stale(_project: Path):
        raise ValueError("stale for the registered score content")

    monkeypatch.setattr(
        "rocksmith_cdlc_generator.eof_workspace_ui.load_current_project_eof_compatibility_report",
        _stale,
    )

    status = build_eof_report_workspace_status(tmp_path)

    assert status.current is False
    assert "stale or unavailable" in status.status_text
    assert "registered score content" in status.status_text


def test_final_workspace_includes_eof_mixin() -> None:
    from rocksmith_cdlc_generator.audio_output_ui import AudioOutputSongWorkspaceWindow

    assert issubclass(AudioOutputSongWorkspaceWindow, EOFWorkspaceMixin)
