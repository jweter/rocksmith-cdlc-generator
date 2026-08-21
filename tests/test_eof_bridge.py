from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.eof_bridge import (
    EOFBridgeError,
    build_eof_launch_command,
    discover_eof_executable,
    resolve_registered_score_for_eof,
)
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.score_source import ProjectScoreSource, ScoreTrackCandidate


def _project_with_gp5(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text("{}", encoding="utf-8")
    stored = project / "sources" / "score" / "original" / "song.gp5"
    stored.parent.mkdir(parents=True)
    stored.write_bytes(b"gp5-test")
    ProjectScoreSource(
        source_filename="song.gp5",
        source_sha256=sha256_file(stored),
        source_format="gp5",
        imported_relative_path=str(stored.relative_to(project)),
        tracks=[ScoreTrackCandidate(source_track_index=0, name="Bass", note_count=1)],
    ).write_json(project / "sources" / "score" / "source.json")
    return project, stored


def test_resolves_verified_registered_gp_score(tmp_path: Path) -> None:
    project, stored = _project_with_gp5(tmp_path)

    assert resolve_registered_score_for_eof(project) == stored.resolve()


def test_builds_eof_command_from_explicit_executable(tmp_path: Path) -> None:
    project, stored = _project_with_gp5(tmp_path)
    eof = tmp_path / "EOF" / "eof.exe"
    eof.parent.mkdir()
    eof.write_bytes(b"placeholder")

    command = build_eof_launch_command(project, eof_executable=eof)

    assert command == [str(eof.resolve()), str(stored.resolve())]


def test_discovers_eof_from_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    eof = tmp_path / "eof.exe"
    eof.write_bytes(b"placeholder")
    monkeypatch.setenv("ROCKSMITH_CDLC_EOF_EXE", str(eof))
    monkeypatch.delenv("EOF_EXE", raising=False)
    monkeypatch.setattr("rocksmith_cdlc_generator.eof_bridge.shutil.which", lambda _: None)

    assert discover_eof_executable() == eof.resolve()


def test_missing_eof_has_actionable_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, _ = _project_with_gp5(tmp_path)
    monkeypatch.delenv("ROCKSMITH_CDLC_EOF_EXE", raising=False)
    monkeypatch.delenv("EOF_EXE", raising=False)
    monkeypatch.setattr("rocksmith_cdlc_generator.eof_bridge.shutil.which", lambda _: None)

    with pytest.raises(EOFBridgeError, match="ROCKSMITH_CDLC_EOF_EXE"):
        build_eof_launch_command(project)
