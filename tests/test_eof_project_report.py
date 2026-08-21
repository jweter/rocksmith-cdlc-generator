from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import rocksmith_cdlc_generator.eof_project_report as project_report
from rocksmith_cdlc_generator.eof_project_report import (
    EOF_PROJECT_REPORT_PATH,
    EOFProjectCompatibilityReport,
    write_project_eof_compatibility_report,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "eof" / "synthetic-gp5-reference.json"
_SCORE = Path(__file__).parent / "fixtures" / "eof" / "synthetic.gp5"


def _project_with_score(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text("{}\n", encoding="utf-8")
    score = project / "sources" / "registered" / "synthetic.gp5"
    score.parent.mkdir(parents=True)
    shutil.copyfile(_SCORE, score)
    monkeypatch.setattr(project_report, "resolve_registered_score_for_eof", lambda _: score)
    return project, score


def test_writes_source_bound_project_local_report_without_mutating_score(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, score = _project_with_score(tmp_path, monkeypatch)
    before = score.read_bytes()

    destination, report = write_project_eof_compatibility_report(
        project,
        _FIXTURE,
        instrument="bass",
    )

    assert destination == project / EOF_PROJECT_REPORT_PATH
    assert report.matched is True
    assert report.score_relative_path == "sources/registered/synthetic.gp5"
    assert score.read_bytes() == before
    persisted = EOFProjectCompatibilityReport.model_validate_json(
        destination.read_text(encoding="utf-8")
    )
    assert persisted == report


def test_stale_fixture_fails_closed_before_report_is_written(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, _score = _project_with_score(tmp_path, monkeypatch)
    stale_fixture = tmp_path / "stale-reference.json"
    payload = _FIXTURE.read_text(encoding="utf-8").replace(
        '"score_sha256": "690da94efe67f3ac4546b582da64b7989ab765f5f039131785c8637a6592314f"',
        '"score_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"',
    )
    stale_fixture.write_text(payload, encoding="utf-8")

    with pytest.raises(ValueError, match="stale or belongs to a different score"):
        write_project_eof_compatibility_report(
            project,
            stale_fixture,
            instrument="bass",
        )

    assert not (project / EOF_PROJECT_REPORT_PATH).exists()


def test_negative_timing_tolerance_fails_without_persisting_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, _score = _project_with_score(tmp_path, monkeypatch)

    with pytest.raises(ValueError, match="timing tolerance must be non-negative"):
        write_project_eof_compatibility_report(
            project,
            _FIXTURE,
            instrument="bass",
            timing_tolerance_seconds=-0.1,
        )

    assert not (project / EOF_PROJECT_REPORT_PATH).exists()
