from pathlib import Path
import os

import pytest

from rocksmith_cdlc_generator.printed_score_desktop_actions import (
    PrintedScoreDesktopActionError,
    latest_reviewed_fixture,
    recognition_candidate_path,
)
from rocksmith_cdlc_generator.score_measure_recognition import PrintedScoreRecognitionCandidateSet


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
    recognition = tmp_path / "derived" / "printed-score" / "recognition"
    recognition.mkdir(parents=True)
    older = recognition / "older-reviewed-fixture.json"
    newer = recognition / "newer-reviewed-fixture.json"
    older.write_text("{}", encoding="utf-8")
    newer.write_text("{}", encoding="utf-8")
    os.utime(older, (1, 1))
    os.utime(newer, (2, 2))
    assert latest_reviewed_fixture(tmp_path) == newer


def test_latest_reviewed_fixture_requires_completed_review(tmp_path: Path) -> None:
    with pytest.raises(PrintedScoreDesktopActionError, match="finish measure review"):
        latest_reviewed_fixture(tmp_path)
