from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import rocksmith_cdlc_generator.eof_export_boundary_project as project_report
from rocksmith_cdlc_generator.eof_export_boundary_project import (
    EOF_EXPORT_BOUNDARY_REPORT_PATH,
    write_project_eof_export_boundary_report,
)


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text("{}\n", encoding="utf-8")
    return project


def test_write_report_uses_reviewed_export_boundary_analyzer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project(tmp_path)
    calls: list[tuple[Path, object, float]] = []
    report = SimpleNamespace(model_dump_json=lambda indent=2: '{"schema_version":1}')

    def analyze(project_dir: Path, role: object, *, overlap_tolerance_seconds: float):
        calls.append((project_dir, role, overlap_tolerance_seconds))
        return report

    monkeypatch.setattr(project_report, "analyze_reviewed_export_boundaries", analyze)

    destination, returned = write_project_eof_export_boundary_report(
        project, instrument="lead", overlap_tolerance_seconds=0.01
    )

    assert destination == project / EOF_EXPORT_BOUNDARY_REPORT_PATH
    assert destination.read_text(encoding="utf-8") == '{"schema_version":1}\n'
    assert returned is report
    assert calls[0][0] == project.resolve()
    assert getattr(calls[0][1], "value") == "lead"
    assert calls[0][2] == pytest.approx(0.01)


def test_rejects_non_project_directory(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(FileNotFoundError, match="Not a CDLC project"):
        write_project_eof_export_boundary_report(plain)
