from __future__ import annotations

import json
from pathlib import Path

import pytest

import rocksmith_cdlc_generator.private_score_bundle_cli as cli
from rocksmith_cdlc_generator.score_measure_recognition import (
    PrintedScoreRecognitionCandidateSet,
    RecognizedMeasureCandidate,
    VisionCandidateEvent,
    VisionMeasureResponse,
)


def _candidate_set() -> PrintedScoreRecognitionCandidateSet:
    response = VisionMeasureResponse(
        events=[
            VisionCandidateEvent(
                kind="note",
                beat=1,
                duration_beats=1,
                string=0,
                fret=5,
                notated_midi=43,
                confidence=0.95,
            ),
            VisionCandidateEvent(
                kind="rest",
                beat=2,
                duration_beats=1,
                confidence=0.92,
            ),
            VisionCandidateEvent(
                kind="note",
                beat=3,
                duration_beats=2,
                string=1,
                fret=0,
                notated_midi=45,
                confidence=0.96,
            ),
        ],
        confidence=0.94,
    )
    return PrintedScoreRecognitionCandidateSet(
        model="gemma3:4b",
        bundle_id="TEST",
        printed_page=2,
        source_sha256="a" * 64,
        derivative_sha256="b" * 64,
        derivative_relative_path="derived/printed-score/preprocessed/page-002.png",
        tuning_midi=[38, 45, 50, 55],
        time_signature_numerator=4,
        time_signature_denominator=4,
        measures=[
            RecognizedMeasureCandidate(
                measure_index=0,
                system_index=0,
                region=(100, 200, 900, 400),
                geometry_confidence=0.9,
                geometry_review_required=False,
                response=response,
                review_required=True,
            )
        ],
    )


def test_recognize_cli_can_emit_private_unreviewed_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    candidates = _candidate_set()

    monkeypatch.setattr(
        cli,
        "recognize_score_measure_candidates",
        lambda *_args, **_kwargs: candidates,
    )

    assert (
        cli.main(
            [
                "recognize-measures",
                str(project),
                "--page",
                "2",
                "--limit",
                "1",
                "--expected-systems",
                "1",
                "--bpm",
                "80",
            ]
        )
        == 0
    )

    expected = (
        project
        / "derived"
        / "printed-score"
        / "recognition"
        / "page-002-bbbbbbbbbbbb-unreviewed-fixture.json"
    )
    assert expected.is_file()
    payload = json.loads(expected.read_text(encoding="utf-8"))
    page = payload["pages"][0]
    assert all(event["review_required"] for event in page["events"])
    assert all(not event["human_reviewed"] for event in page["events"])
    assert all(rest["review_required"] for rest in page["rests"])
    assert all(not rest["human_reviewed"] for rest in page["rests"])
    assert "UNREVIEWED_FIXTURE=" in capsys.readouterr().out


def test_fixture_output_cannot_escape_private_project(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    with pytest.raises(ValueError, match="inside the private project"):
        cli._write_unreviewed_fixture(
            project,
            _candidate_set(),
            bpm=80.0,
            output=tmp_path / "outside.json",
        )


def test_fixture_output_requires_bpm(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cli.main(
            [
                "recognize-measures",
                "project",
                "--page",
                "2",
                "--fixture-output",
                "derived/test.json",
            ]
        )
    assert "requires --bpm" in capsys.readouterr().err
