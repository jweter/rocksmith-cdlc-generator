from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import rocksmith_cdlc_generator.eof_short_note_truncation_project as project_report
from rocksmith_cdlc_generator.eof_short_note_truncation_project import (
    EOF_SHORT_NOTE_TRUNCATION_REPORT_PATH,
    build_project_eof_short_note_truncation_report,
    write_project_eof_short_note_truncation_report,
)
from rocksmith_cdlc_generator.eof_short_note_truncation_check import EOFShortNoteTruncationReport

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


def test_build_report_flags_the_palm_muted_single_note_eof_would_truncate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, _score = _project_with_score(tmp_path, monkeypatch)

    report = build_project_eof_short_note_truncation_report(project, instrument="bass")

    assert report.note_count == 2
    assert report.eof_truncated_count == 1
    assert report.truncation_matches_eof_preferences is False
    assert len(report.mismatches) == 1
    truncated = report.mismatches[0].event
    assert truncated.string_number == 4
    assert truncated.fret == 0
    assert truncated.is_fully_muted_or_palm_muted is True
    assert truncated.eof_would_truncate is True
    assert truncated.eof_predicted_sustain_seconds == pytest.approx(0.001)


def test_write_report_persists_it_under_the_project_review_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, score = _project_with_score(tmp_path, monkeypatch)
    before = score.read_bytes()

    destination, report = write_project_eof_short_note_truncation_report(
        project, instrument="bass"
    )

    assert destination == project / EOF_SHORT_NOTE_TRUNCATION_REPORT_PATH
    assert destination.is_file()
    assert score.read_bytes() == before
    persisted = EOFShortNoteTruncationReport.model_validate_json(
        destination.read_text(encoding="utf-8")
    )
    assert persisted == report


def test_rejects_a_directory_that_is_not_a_cdlc_project(tmp_path: Path) -> None:
    not_a_project = tmp_path / "plain-directory"
    not_a_project.mkdir()

    with pytest.raises(FileNotFoundError, match="Not a CDLC project"):
        write_project_eof_short_note_truncation_report(not_a_project, instrument="bass")
