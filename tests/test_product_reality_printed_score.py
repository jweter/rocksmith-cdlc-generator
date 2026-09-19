from __future__ import annotations

from pathlib import Path

import pytest

import rocksmith_cdlc_generator.product_reality_printed_score as subject
from rocksmith_cdlc_generator.printed_score_review import (
    create_review_draft,
    save_review_record,
)
from rocksmith_cdlc_generator.score_measure_recognition import (
    PRIVATE_RECOGNITION_RELATIVE_PATH,
    PrintedScoreRecognitionCandidateSet,
    RecognizedMeasureCandidate,
    VisionCandidateEvent,
    VisionMeasureResponse,
)

_HASH = "a" * 64


def _event(*, confidence: float = 0.95) -> VisionCandidateEvent:
    return VisionCandidateEvent(
        kind="note",
        beat=1.0,
        # Covers the whole 4/4 measure and supplies tuning_midi[0] (40) + fret (2) as a
        # matching independent pitch estimate, so this event is genuinely clean under the
        # real deterministic-warning rules (coverage and pitch cross-check alike) now that
        # collect_printed_score_recognition_evidence recomputes warnings on load.
        duration_beats=4.0,
        string=0,
        fret=2,
        notated_midi=42,
        confidence=confidence,
    )


def _measure(measure_index: int) -> RecognizedMeasureCandidate:
    return RecognizedMeasureCandidate(
        measure_index=measure_index,
        system_index=0,
        region=(0, 0, 10, 10),
        geometry_confidence=0.95,
        geometry_review_required=False,
        response=VisionMeasureResponse(events=[_event()], confidence=0.95),
    )


def _write_candidate(project_dir: Path, *, printed_page: int = 1) -> Path:
    candidates = PrintedScoreRecognitionCandidateSet(
        model="gemma3:4b",
        bundle_id="bundle-1",
        printed_page=printed_page,
        source_sha256=_HASH,
        derivative_sha256=_HASH,
        derivative_relative_path=f"page-{printed_page:03d}.png",
        tuning_midi=[40, 45, 50, 55, 59, 64],
        time_signature_numerator=4,
        time_signature_denominator=4,
        measures=[_measure(0)],
    )
    destination = (
        project_dir
        / PRIVATE_RECOGNITION_RELATIVE_PATH
        / f"page-{printed_page:03d}-candidate.json"
    )
    return candidates.write_json(destination)


def test_missing_recognition_directory_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        subject.collect_printed_score_recognition_evidence(tmp_path)


def test_unreviewed_candidate_is_review_required(tmp_path: Path) -> None:
    _write_candidate(tmp_path)

    evidence = subject.collect_printed_score_recognition_evidence(tmp_path)

    assert evidence.status == "REVIEW_REQUIRED"
    assert evidence.candidate_page_count == 1
    assert evidence.reviewed_page_count == 0
    assert evidence.unreadable_candidate_count == 0
    assert str(tmp_path) not in evidence.message


def test_fully_reviewed_candidate_passes(tmp_path: Path) -> None:
    candidate_path = _write_candidate(tmp_path)
    draft = create_review_draft(tmp_path, candidate_path.relative_to(tmp_path))
    reviewed_measures = [
        measure.model_copy(update={"status": "approved"}) for measure in draft.measures
    ]
    draft = draft.model_copy(update={"measures": reviewed_measures})
    save_review_record(tmp_path, draft)

    evidence = subject.collect_printed_score_recognition_evidence(tmp_path)

    assert evidence.status == "PASS"
    assert evidence.candidate_page_count == 1
    assert evidence.reviewed_page_count == 1
    assert evidence.mean_clean_measure_fraction == pytest.approx(1.0)


def test_unreadable_candidate_file_is_review_required_without_private_detail(
    tmp_path: Path,
) -> None:
    destination = (
        tmp_path / PRIVATE_RECOGNITION_RELATIVE_PATH / "page-001-candidate.json"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("not valid json {{{", encoding="utf-8")

    evidence = subject.collect_printed_score_recognition_evidence(tmp_path)

    assert evidence.status == "REVIEW_REQUIRED"
    assert evidence.unreadable_candidate_count == 1
    assert str(tmp_path) not in evidence.message


def test_review_record_missing_a_measure_is_not_counted_as_reviewed(
    tmp_path: Path,
) -> None:
    candidates = PrintedScoreRecognitionCandidateSet(
        model="gemma3:4b",
        bundle_id="bundle-1",
        printed_page=1,
        source_sha256=_HASH,
        derivative_sha256=_HASH,
        derivative_relative_path="page-001.png",
        tuning_midi=[40, 45, 50, 55, 59, 64],
        time_signature_numerator=4,
        time_signature_denominator=4,
        measures=[_measure(0), _measure(1)],
    )
    destination = (
        tmp_path / PRIVATE_RECOGNITION_RELATIVE_PATH / "page-001-candidate.json"
    )
    candidate_path = candidates.write_json(destination)

    draft = create_review_draft(tmp_path, candidate_path.relative_to(tmp_path))
    assert len(draft.measures) == 2

    # Only measure 0 is retained (approved); measure 1 is dropped from the list
    # entirely rather than left "pending" -- this must not read as complete.
    truncated = draft.model_copy(
        update={
            "measures": [draft.measures[0].model_copy(update={"status": "approved"})]
        }
    )
    save_review_record(tmp_path, truncated)

    evidence = subject.collect_printed_score_recognition_evidence(tmp_path)

    assert evidence.status == "REVIEW_REQUIRED"
    assert evidence.reviewed_page_count == 0


def test_multiple_pages_require_every_page_reviewed_to_pass(tmp_path: Path) -> None:
    first = _write_candidate(tmp_path, printed_page=1)
    _write_candidate(tmp_path, printed_page=2)

    draft = create_review_draft(tmp_path, first.relative_to(tmp_path))
    reviewed_measures = [
        measure.model_copy(update={"status": "approved"}) for measure in draft.measures
    ]
    draft = draft.model_copy(update={"measures": reviewed_measures})
    save_review_record(tmp_path, draft)

    evidence = subject.collect_printed_score_recognition_evidence(tmp_path)

    assert evidence.status == "REVIEW_REQUIRED"
    assert evidence.candidate_page_count == 2
    assert evidence.reviewed_page_count == 1
