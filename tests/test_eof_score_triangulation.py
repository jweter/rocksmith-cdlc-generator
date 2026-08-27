from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import rocksmith_cdlc_generator.eof_score_triangulation as triangulation
from rocksmith_cdlc_generator.eof_score_triangulation import (
    EOF_SCORE_TRIANGULATION_REPORT_PATH,
    _compare_role,
    load_current_project_eof_score_triangulation_report,
    write_project_eof_score_triangulation_report,
)
from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTrack,
)


_SCORE = Path(__file__).parent / "fixtures" / "eof" / "synthetic.gp5"


def _project_with_score(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.json").write_text("{}\n", encoding="utf-8")
    score = project / "sources" / "registered" / "synthetic.gp5"
    score.parent.mkdir(parents=True)
    shutil.copyfile(_SCORE, score)
    monkeypatch.setattr(triangulation, "resolve_registered_score_for_eof", lambda _: score)
    return project, score


def test_identical_private_gp_is_structurally_close_and_persisted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, _registered = _project_with_score(tmp_path, monkeypatch)
    alternate = tmp_path / "alternate.gp5"
    shutil.copyfile(_SCORE, alternate)

    destination, report = write_project_eof_score_triangulation_report(project, alternate)

    assert destination == project / EOF_SCORE_TRIANGULATION_REPORT_PATH
    assert report.alternate_score_filename == "alternate.gp5"
    assert report.roles
    bass = next(item for item in report.roles if item.instrument == "bass")
    assert bass.structurally_close is True
    assert bass.first_playable_delta_seconds == pytest.approx(0.0)
    assert bass.registered_note_count == bass.alternate_note_count
    assert load_current_project_eof_score_triangulation_report(project) == report


def test_report_fails_closed_when_private_alternate_score_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, _registered = _project_with_score(tmp_path, monkeypatch)
    alternate = tmp_path / "alternate.gp5"
    shutil.copyfile(_SCORE, alternate)
    write_project_eof_score_triangulation_report(project, alternate)
    alternate.write_bytes(alternate.read_bytes() + b"stale")

    with pytest.raises(ValueError, match="alternate GP file moved or changed"):
        load_current_project_eof_score_triangulation_report(project)


def _note(start: float, *, midi: int = 59, string_index: int = 4, fret: int = 8) -> SourceNoteEvent:
    return SourceNoteEvent(
        start_seconds=start,
        duration_seconds=0.25,
        midi=midi,
        string_index=string_index,
        fret=fret,
        import_confidence=1.0,
    )


def _source(starts: list[float]) -> ImportedSource:
    return ImportedSource(
        provenance=SourceProvenance(
            source_type="gp5",
            source_filename="fixture.gp5",
            source_sha256="a" * 64,
            importer="fixture",
            importer_version="1",
        ),
        tracks=[
            SourceTrack(
                source_track_index=1,
                name="Lead",
                instrument="lead",
                tuning_midi=[40, 45, 50, 55, 59, 64],
                notes=[_note(start) for start in starts],
            )
        ],
    )


def test_structurally_same_notes_with_shifted_source_time_are_flagged() -> None:
    registered = _source([4.0, 5.0, 6.0, 7.0])
    alternate = _source([0.0, 1.0, 2.0, 3.0])

    comparison = _compare_role(registered, alternate, instrument="lead")

    assert comparison.coordinate_prefix_matches == 4
    assert comparison.coordinate_prefix_compared == 4
    assert comparison.onset_prefix_matches == 0
    assert comparison.first_playable_delta_seconds == pytest.approx(-4.0)
    assert comparison.median_prefix_onset_delta_seconds == pytest.approx(-4.0)
    assert comparison.max_prefix_onset_delta_seconds == pytest.approx(4.0)
    assert comparison.structurally_close is False
