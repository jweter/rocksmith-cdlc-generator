import json
import os
from pathlib import Path

import pytest

from rocksmith_cdlc_generator.printed_score_desktop_actions import (
    PrintedScoreDesktopActionError,
    _write_practice_build_authority,
    latest_reviewed_fixture,
    practice_build_is_current,
    recognition_candidate_path,
)
from rocksmith_cdlc_generator.score_measure_recognition import PrintedScoreRecognitionCandidateSet


def _write_movement_authority(project_dir: Path) -> None:
    (project_dir / "printed-score-project.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "bundle_id": "TEST",
                "instrument": "bass",
                "movement_id": "prelude",
                "movement_title": "Prelude",
                "start_page": 2,
                "end_page": 2,
            }
        ),
        encoding="utf-8",
    )


def _practice_outputs(project_dir: Path) -> dict[str, Path]:
    output_dir = project_dir / "printed_notation"
    output_dir.mkdir(parents=True, exist_ok=True)
    xml = output_dir / "arr_bass_RS2.xml"
    click = output_dir / "click.wav"
    xml.write_text("<song />\n", encoding="utf-8")
    click.write_bytes(b"RIFF-test-click")
    return {"xml": xml, "click_wav": click}


def test_recognition_candidate_path_matches_written_contract(tmp_path: Path) -> None:
    candidates = PrintedScoreRecognitionCandidateSet(
        model="local-model",
        bundle_id="TEST",
        printed_page=2,
        source_sha256="a" * 64,
        derivative_sha256="b" * 64,
        derivative_relative_path="derived/printed-score/preprocessed/page-002.png",
        tuning_midi=[38, 45, 50, 55],
        time_signature_numerator=4,
        time_signature_denominator=4,
        measures=[],
    )
    assert recognition_candidate_path(tmp_path, candidates) == (
        tmp_path
        / "derived"
        / "printed-score"
        / "recognition"
        / "page-002-bbbbbbbbbbbb-candidates.json"
    )


def test_latest_reviewed_fixture_selects_newest_private_fixture(tmp_path: Path) -> None:
    _write_movement_authority(tmp_path)
    recognition = tmp_path / "derived" / "printed-score" / "recognition"
    recognition.mkdir(parents=True)
    older = recognition / "page-002-aaaaaaaaaaaa-reviewed-fixture.json"
    newer = recognition / "page-002-bbbbbbbbbbbb-reviewed-fixture.json"
    older.write_text("{}", encoding="utf-8")
    newer.write_text("{}", encoding="utf-8")
    os.utime(older, (1, 1))
    os.utime(newer, (2, 2))
    assert latest_reviewed_fixture(tmp_path) == newer


def test_latest_reviewed_fixture_requires_completed_review(tmp_path: Path) -> None:
    with pytest.raises(PrintedScoreDesktopActionError, match="finish measure review"):
        latest_reviewed_fixture(tmp_path)


def test_practice_readiness_invalidates_when_reviewed_fixture_changes_in_place(
    tmp_path: Path,
) -> None:
    _write_movement_authority(tmp_path)
    recognition = tmp_path / "derived" / "printed-score" / "recognition"
    recognition.mkdir(parents=True)
    fixture = recognition / "page-002-aaaaaaaaaaaa-reviewed-fixture.json"
    fixture.write_text('{"review": 1}\n', encoding="utf-8")
    outputs = _practice_outputs(tmp_path)

    _write_practice_build_authority(
        tmp_path,
        fixture,
        outputs,
        count_in_measures=2,
        subdivision=None,
    )
    assert practice_build_is_current(tmp_path)

    fixture.write_text('{"review": 2}\n', encoding="utf-8")
    assert not practice_build_is_current(tmp_path)


def test_practice_readiness_invalidates_when_new_review_becomes_authoritative(
    tmp_path: Path,
) -> None:
    _write_movement_authority(tmp_path)
    recognition = tmp_path / "derived" / "printed-score" / "recognition"
    recognition.mkdir(parents=True)
    older = recognition / "page-002-aaaaaaaaaaaa-reviewed-fixture.json"
    older.write_text('{"review": "older"}\n', encoding="utf-8")
    os.utime(older, (1, 1))
    outputs = _practice_outputs(tmp_path)
    _write_practice_build_authority(
        tmp_path,
        older,
        outputs,
        count_in_measures=2,
        subdivision=None,
    )
    assert practice_build_is_current(tmp_path)

    newer = recognition / "page-002-bbbbbbbbbbbb-reviewed-fixture.json"
    newer.write_text('{"review": "newer"}\n', encoding="utf-8")
    os.utime(newer, (2, 2))
    assert not practice_build_is_current(tmp_path)


def test_practice_readiness_invalidates_when_generated_output_changes(tmp_path: Path) -> None:
    _write_movement_authority(tmp_path)
    recognition = tmp_path / "derived" / "printed-score" / "recognition"
    recognition.mkdir(parents=True)
    fixture = recognition / "page-002-aaaaaaaaaaaa-reviewed-fixture.json"
    fixture.write_text('{"review": 1}\n', encoding="utf-8")
    outputs = _practice_outputs(tmp_path)
    _write_practice_build_authority(
        tmp_path,
        fixture,
        outputs,
        count_in_measures=2,
        subdivision=None,
    )
    assert practice_build_is_current(tmp_path)

    outputs["xml"].write_text("<song changed='true' />\n", encoding="utf-8")
    assert not practice_build_is_current(tmp_path)


def test_practice_readiness_treats_undecodable_authority_receipt_as_stale(
    tmp_path: Path,
) -> None:
    _write_movement_authority(tmp_path)
    recognition = tmp_path / "derived" / "printed-score" / "recognition"
    recognition.mkdir(parents=True)
    fixture = recognition / "page-002-aaaaaaaaaaaa-reviewed-fixture.json"
    fixture.write_text('{"review": 1}\n', encoding="utf-8")
    outputs = _practice_outputs(tmp_path)
    authority_path = _write_practice_build_authority(
        tmp_path,
        fixture,
        outputs,
        count_in_measures=2,
        subdivision=None,
    )
    assert practice_build_is_current(tmp_path)

    authority_path.write_bytes(b"\xff\xfe\xfa")
    assert not practice_build_is_current(tmp_path)
