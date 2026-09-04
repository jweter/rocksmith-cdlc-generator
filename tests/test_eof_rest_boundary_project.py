from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import rocksmith_cdlc_generator.eof_rest_boundary_project as project_report
from rocksmith_cdlc_generator.eof_rest_boundary_check import EOFRestBoundaryReport
from rocksmith_cdlc_generator.eof_rest_boundary_project import (
    EOF_REST_BOUNDARY_REPORT_PATH,
    build_project_eof_rest_boundary_report,
    write_project_eof_rest_boundary_report,
)

_SCORE = Path(__file__).parent / "fixtures" / "eof" / "synthetic.gp5"


def _project_with_score(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path]:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text("{}\n", encoding="utf-8")
    score = project / "sources" / "registered" / "synthetic.gp5"
    score.parent.mkdir(parents=True)
    shutil.copyfile(_SCORE, score)
    monkeypatch.setattr(
        project_report, "resolve_registered_score_for_eof", lambda _: score
    )
    return project, score


def test_build_report_finds_no_explicit_rests_in_the_synthetic_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, _score = _project_with_score(tmp_path, monkeypatch)

    report = build_project_eof_rest_boundary_report(project, instrument="bass")

    assert report.note_count == 2
    assert report.explicit_rest_count == 0
    assert report.boundaries_respected is True
    assert report.violations == []


def test_write_report_persists_it_under_the_project_review_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, score = _project_with_score(tmp_path, monkeypatch)
    before = score.read_bytes()

    destination, report = write_project_eof_rest_boundary_report(project, instrument="bass")

    assert destination == project / EOF_REST_BOUNDARY_REPORT_PATH
    assert destination.is_file()
    assert score.read_bytes() == before
    persisted = EOFRestBoundaryReport.model_validate_json(
        destination.read_text(encoding="utf-8")
    )
    assert persisted == report


def test_rejects_a_directory_that_is_not_a_cdlc_project(tmp_path: Path) -> None:
    not_a_project = tmp_path / "plain-directory"
    not_a_project.mkdir()

    with pytest.raises(FileNotFoundError, match="Not a CDLC project"):
        write_project_eof_rest_boundary_report(not_a_project, instrument="bass")
