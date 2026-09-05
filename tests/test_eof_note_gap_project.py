from __future__ import annotations

from pathlib import Path

import pytest

import rocksmith_cdlc_generator.eof_note_gap_project as project_report
from rocksmith_cdlc_generator.eof_note_gap_project import (
    EOF_NOTE_GAP_REPORT_PATH,
    build_project_eof_note_gap_report,
    write_project_eof_note_gap_report,
)
from rocksmith_cdlc_generator.eof_note_gap_check import EOFNoteGapReport
from rocksmith_cdlc_generator.reviewed_export_events import (
    ReviewedExportArrangement,
    ReviewedExportNote,
)
from rocksmith_cdlc_generator.score_source import ArrangementRole
from rocksmith_cdlc_generator.source_import import SourceTrustClass

_SHA = "ab" * 32


def _note(*, index: int, start: float, duration: float, string_index: int | None) -> ReviewedExportNote:
    return ReviewedExportNote(
        source_event_index=index,
        source_start_seconds=start,
        source_duration_seconds=duration,
        reviewed_start_seconds=start,
        reviewed_duration_seconds=duration,
        midi=40,
        string_index=string_index,
        fret=0 if string_index is not None else None,
        import_confidence=1.0,
        trust_class=SourceTrustClass.symbolic_verified,
        position_ready=string_index is not None,
    )


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text("{}\n", encoding="utf-8")
    return project


def _arrangement(notes: list[ReviewedExportNote], *, role: ArrangementRole) -> ReviewedExportArrangement:
    return ReviewedExportArrangement(
        role=role,
        source_track_index=0,
        source_output_json="sources/fanout/lead.json",
        source_output_sha256=_SHA,
        recording_sha256=_SHA,
        score_sha256=_SHA,
        notes=notes,
    )


def _stub_reviewed_export_arrangement(
    monkeypatch: pytest.MonkeyPatch, arrangement: ReviewedExportArrangement
) -> None:
    def fake(_project: Path, role: ArrangementRole) -> ReviewedExportArrangement:
        assert role is arrangement.role
        return arrangement

    monkeypatch.setattr(project_report, "reviewed_export_arrangement", fake)


def test_build_report_finds_no_overlap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _project(tmp_path)
    arrangement = _arrangement(
        [
            _note(index=0, start=0.0, duration=0.5, string_index=1),
            _note(index=1, start=1.0, duration=0.5, string_index=1),
        ],
        role=ArrangementRole.bass,
    )
    _stub_reviewed_export_arrangement(monkeypatch, arrangement)

    report = build_project_eof_note_gap_report(project, instrument="bass")

    assert report.gaps_respected is True
    assert report.violations == []


def test_build_report_flags_a_same_string_overlap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _project(tmp_path)
    arrangement = _arrangement(
        [
            _note(index=0, start=0.0, duration=1.5, string_index=2),
            _note(index=1, start=1.0, duration=0.5, string_index=2),
        ],
        role=ArrangementRole.lead,
    )
    _stub_reviewed_export_arrangement(monkeypatch, arrangement)

    report = build_project_eof_note_gap_report(project, instrument="lead")

    assert report.gaps_respected is False
    assert len(report.violations) == 1


def test_write_report_persists_it_under_the_project_review_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project(tmp_path)
    arrangement = _arrangement(
        [_note(index=0, start=0.0, duration=0.5, string_index=1)],
        role=ArrangementRole.rhythm,
    )
    _stub_reviewed_export_arrangement(monkeypatch, arrangement)

    destination, report = write_project_eof_note_gap_report(project, instrument="rhythm")

    assert destination == project / EOF_NOTE_GAP_REPORT_PATH
    assert destination.is_file()
    persisted = EOFNoteGapReport.model_validate_json(destination.read_text(encoding="utf-8"))
    assert persisted == report


def test_rejects_a_directory_that_is_not_a_cdlc_project(tmp_path: Path) -> None:
    not_a_project = tmp_path / "plain-directory"
    not_a_project.mkdir()

    with pytest.raises(FileNotFoundError, match="Not a CDLC project"):
        write_project_eof_note_gap_report(not_a_project, instrument="bass")
