from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

import rocksmith_cdlc_generator.eof_hand_position_project as hand_project
from rocksmith_cdlc_generator.eof_hand_position_observation import (
    EOFHandPositionFixture,
    EOFHandPositionObservation,
    source_event_sha256,
)
from rocksmith_cdlc_generator.eof_hand_position_project import (
    EOF_HAND_POSITION_STATUS_PATH,
    EOFProjectHandPositionStatus,
    load_current_project_eof_hand_position_status,
    write_project_eof_hand_position_status,
)
from rocksmith_cdlc_generator.guitarpro_import import import_guitarpro
from rocksmith_cdlc_generator.score_source import (
    ArrangementRole,
    ProjectScoreSource,
    ScoreArrangementMapping,
    ScoreTrackCandidate,
)

_SCORE = Path(__file__).parent / "fixtures" / "eof" / "synthetic.gp5"


def _write_score_contract(
    project: Path,
    score: Path,
    *,
    bass_track: int = 0,
    human_confirmed: bool = True,
) -> None:
    ProjectScoreSource(
        source_filename=score.name,
        source_sha256=hashlib.sha256(score.read_bytes()).hexdigest(),
        source_format="gp5",
        imported_relative_path=score.relative_to(project).as_posix(),
        tracks=[
            ScoreTrackCandidate(source_track_index=0, name="Bass", note_count=2),
            ScoreTrackCandidate(source_track_index=1, name="Alternate", note_count=2),
        ],
        arrangement_mappings=[
            ScoreArrangementMapping(
                role=ArrangementRole.bass,
                source_track_index=bass_track,
                confidence=1.0,
                basis=["test mapping"],
                human_confirmed=human_confirmed,
            )
        ],
    ).write_json(project / "sources" / "score" / "source.json")


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
        hand_project, "resolve_registered_score_for_eof", lambda _: score
    )
    _write_score_contract(project, score)
    return project, score


def _fixture(path: Path, score: Path) -> Path:
    imported = import_guitarpro(score, track_index=0, instrument="bass")
    event = imported.tracks[0].notes[1]
    fixture = EOFHandPositionFixture(
        fixture_id="synthetic-bass-hand-position",
        score_sha256=imported.provenance.source_sha256,
        score_format="gp5",
        source_track_index=0,
        eof_version="manual-review-pending",
        evidence_note="Synthetic hand-position evidence for project binding tests.",
        observations=(
            EOFHandPositionObservation(start_seconds=0.0, fret=0),
            EOFHandPositionObservation(
                start_seconds=0.5,
                fret=2,
                source_event_index=1,
                source_event_sha256=source_event_sha256(event),
            ),
        ),
    )
    path.write_text(fixture.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def test_writes_project_local_hand_position_status_without_mutating_score(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, score = _project_with_score(tmp_path, monkeypatch)
    fixture = _fixture(tmp_path / "hand-positions.json", score)
    before = score.read_bytes()

    destination, status = write_project_eof_hand_position_status(
        project, fixture, instrument="bass"
    )

    assert destination == project / EOF_HAND_POSITION_STATUS_PATH
    assert status.evidence.observation_count == 2
    assert status.evidence.source_track_index == 0
    assert status.importer == "pyguitarpro-adapter"
    assert score.read_bytes() == before
    persisted = EOFProjectHandPositionStatus.model_validate_json(
        destination.read_text(encoding="utf-8")
    )
    assert persisted == status
    assert load_current_project_eof_hand_position_status(project) == status


def test_stale_fixture_fails_before_status_is_written(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, score = _project_with_score(tmp_path, monkeypatch)
    fixture = _fixture(tmp_path / "hand-positions.json", score)
    payload = fixture.read_text(encoding="utf-8").replace(
        '"score_sha256": "690da94efe67f3ac4546b582da64b7989ab765f5f039131785c8637a6592314f"',
        '"score_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"',
    )
    fixture.write_text(payload, encoding="utf-8")

    with pytest.raises(ValueError, match="stale or belongs to a different score"):
        write_project_eof_hand_position_status(project, fixture, instrument="bass")

    assert not (project / EOF_HAND_POSITION_STATUS_PATH).exists()


def test_current_status_fails_closed_after_score_or_importer_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, score = _project_with_score(tmp_path, monkeypatch)
    fixture = _fixture(tmp_path / "hand-positions.json", score)
    write_project_eof_hand_position_status(project, fixture, instrument="bass")

    monkeypatch.setattr(hand_project, "guitarpro_adapter_sha256", lambda: "f" * 64)
    with pytest.raises(ValueError, match="stale for the Guitar Pro adapter"):
        load_current_project_eof_hand_position_status(project)


def test_hand_position_status_requires_current_human_confirmed_role_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, score = _project_with_score(tmp_path, monkeypatch)
    fixture = _fixture(tmp_path / "hand-positions.json", score)

    _write_score_contract(project, score, bass_track=1)
    with pytest.raises(
        ValueError, match="does not match the human-confirmed bass mapping"
    ):
        write_project_eof_hand_position_status(project, fixture, instrument="bass")
    assert not (project / EOF_HAND_POSITION_STATUS_PATH).exists()

    _write_score_contract(project, score)
    write_project_eof_hand_position_status(project, fixture, instrument="bass")
    _write_score_contract(project, score, human_confirmed=False)
    with pytest.raises(ValueError, match="requires a human-confirmed bass mapping"):
        load_current_project_eof_hand_position_status(project)


def test_missing_status_is_explicitly_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, _score = _project_with_score(tmp_path, monkeypatch)
    assert load_current_project_eof_hand_position_status(project) is None
