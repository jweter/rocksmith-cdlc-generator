from __future__ import annotations

from pathlib import Path

from pydantic import TypeAdapter
import pytest

from rocksmith_cdlc_generator.printed_score_review import (
    PrintedScoreReviewError,
    ReviewedScoreEvent,
    ReviewedScoreMeasure,
    create_review_draft,
    materialize_reviewed_fixture,
    save_review_record,
    write_reviewed_fixture,
)
from rocksmith_cdlc_generator.score_measure_recognition import (
    PrintedScoreRecognitionCandidateSet,
    RecognizedMeasureCandidate,
    VisionCandidateEvent,
    VisionMeasureResponse,
)


def _candidate_set() -> PrintedScoreRecognitionCandidateSet:
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
                response=VisionMeasureResponse(
                    confidence=0.94,
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
                            confidence=0.91,
                        ),
                        VisionCandidateEvent(
                            kind="note",
                            beat=3,
                            duration_beats=2,
                            string=1,
                            fret=0,
                            notated_midi=45,
                            confidence=0.93,
                        ),
                    ],
                ),
                review_required=True,
            )
        ],
    )


def _write_candidates(project: Path) -> Path:
    destination = project / "derived" / "printed-score" / "recognition" / "candidates.json"
    destination.parent.mkdir(parents=True)
    destination.write_text(_candidate_set().model_dump_json(indent=2) + "\n", encoding="utf-8")
    return destination


def _replace_measure(record, measure: ReviewedScoreMeasure):
    return record.model_copy(update={"measures": [measure]})


def test_review_draft_is_pending_and_bound_to_candidate_hash(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    candidate_path = _write_candidates(project)

    record = create_review_draft(project, candidate_path)

    assert record.measures[0].status == "pending"
    assert record.all_measures_reviewed is False
    assert record.candidate_file_relative_path == "derived/printed-score/recognition/candidates.json"
    assert len(record.candidate_sha256) == 64
    assert [event.source_event_index for event in record.measures[0].events] == [0, 1, 2]


def test_pending_review_cannot_be_materialized(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    candidate_path = _write_candidates(project)
    record = create_review_draft(project, candidate_path)

    with pytest.raises(PrintedScoreReviewError, match="pending measure review"):
        materialize_reviewed_fixture(project, record, bpm=80)


def test_approved_measure_materializes_user_confirmed_notes_and_rests(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    candidate_path = _write_candidates(project)
    record = create_review_draft(project, candidate_path)
    measure = record.measures[0].model_copy(update={"status": "approved"})
    record = _replace_measure(record, measure)

    fixture = materialize_reviewed_fixture(project, record, bpm=80)

    page = fixture.pages[0]
    assert len(page.events) == 2
    assert len(page.rests) == 1
    assert all(event.human_reviewed for event in page.events)
    assert all(not event.review_required for event in page.events)
    assert all(rest.human_reviewed for rest in page.rests)
    assert all(not rest.review_required for rest in page.rests)
    assert all(event.field_confidence["human_review"] == 1.0 for event in page.events)


def test_corrected_event_is_preserved_as_review_authority(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    candidate_path = _write_candidates(project)
    record = create_review_draft(project, candidate_path)
    original = record.measures[0]
    corrected = original.events[0].model_copy(
        update={"action": "corrected", "fret": 7, "reviewer_note": "fret digit is 7"}
    )
    measure = original.model_copy(
        update={"status": "corrected", "events": [corrected, *original.events[1:]]}
    )
    record = _replace_measure(record, measure)

    fixture = materialize_reviewed_fixture(project, record, bpm=80)

    assert fixture.pages[0].events[0].fret == 7
    assert fixture.pages[0].events[0].human_reviewed is True


def test_stale_candidate_file_invalidates_review(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    candidate_path = _write_candidates(project)
    record = create_review_draft(project, candidate_path)
    measure = record.measures[0].model_copy(update={"status": "approved"})
    record = _replace_measure(record, measure)

    candidate_path.write_text(candidate_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(PrintedScoreReviewError, match="changed after review began"):
        materialize_reviewed_fixture(project, record, bpm=80)


def test_explicit_rest_overlapping_note_is_rejected(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    candidate_path = _write_candidates(project)
    record = create_review_draft(project, candidate_path)
    original = record.measures[0]
    overlap = ReviewedScoreEvent(
        source_event_index=None,
        action="added",
        kind="rest",
        beat=1,
        duration_beats=1,
        original_vision_confidence=None,
    )
    measure = original.model_copy(
        update={"status": "corrected", "events": [*original.events, overlap]}
    )
    record = _replace_measure(record, measure)

    with pytest.raises(PrintedScoreReviewError, match="rest overlapping a note"):
        materialize_reviewed_fixture(project, record, bpm=80)


def test_review_and_reviewed_fixture_outputs_cannot_escape_project(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    candidate_path = _write_candidates(project)
    record = create_review_draft(project, candidate_path)

    with pytest.raises(PrintedScoreReviewError, match="escaped the project"):
        save_review_record(project, record, output=tmp_path / "outside-review.json")

    measure = record.measures[0].model_copy(update={"status": "approved"})
    record = _replace_measure(record, measure)
    with pytest.raises(PrintedScoreReviewError, match="escaped the project"):
        write_reviewed_fixture(
            project,
            record,
            bpm=80,
            output=tmp_path / "outside-fixture.json",
        )
