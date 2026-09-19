from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .hashing import sha256_file
from .printed_score_review import PRIVATE_REVIEW_RELATIVE_PATH, PrintedScoreReviewRecord
from .score_measure_recognition import (
    PRIVATE_RECOGNITION_RELATIVE_PATH,
    PrintedScoreRecognitionCandidateSet,
)
from .score_recognition_quality_metrics import summarize_candidate_set_quality

PrintedScoreProductRealityStatus = Literal["PASS", "REVIEW_REQUIRED"]


class PrintedScoreProductRealityEvidence(BaseModel):
    """Privacy-safe printed-score recognition completeness evidence for Product Reality.

    Exposes only aggregate counts/fractions computed from the recognizer's own deterministic
    output and local review-completion state: no page images, private paths, recognized
    note/fret content, or reviewer notes leave the local evidence boundary. Per
    PROJECT_PLAN.md's printed-notation rule, recognition is evidence extraction, not authority
    by default, so an unreviewed candidate set is REVIEW_REQUIRED, never PASS, regardless of
    its own confidence metrics.
    """

    model_config = ConfigDict(frozen=True)

    status: PrintedScoreProductRealityStatus
    candidate_page_count: int = Field(ge=0)
    reviewed_page_count: int = Field(ge=0)
    unreadable_candidate_count: int = Field(ge=0)
    mean_clean_measure_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    mean_low_confidence_event_fraction: float | None = Field(
        default=None, ge=0.0, le=1.0
    )
    message: str


def _matching_review_record(
    project_root: Path,
    candidate: PrintedScoreRecognitionCandidateSet,
    candidate_sha256: str,
) -> PrintedScoreReviewRecord | None:
    review_path = (
        project_root
        / PRIVATE_REVIEW_RELATIVE_PATH
        / f"page-{candidate.printed_page:03d}-{candidate_sha256[:12]}-review.json"
    )
    if not review_path.is_file():
        return None
    try:
        return PrintedScoreReviewRecord.read_json(review_path)
    except (OSError, ValidationError, ValueError):
        return None


def _review_covers_every_measure(
    candidate: PrintedScoreRecognitionCandidateSet,
    review: PrintedScoreReviewRecord,
) -> bool:
    """Reject a review record whose ``measures`` list omits candidate measures.

    ``PrintedScoreReviewRecord.all_measures_reviewed`` only inspects the measures the
    record itself lists; nothing upstream guarantees that list still matches the
    candidate's full measure set (e.g. a truncated/corrupted save). Without this check
    a record covering only some measures, with none left ``pending``, would be
    indistinguishable from a genuinely complete review.
    """

    candidate_indexes = {measure.measure_index for measure in candidate.measures}
    review_indexes = {measure.measure_index for measure in review.measures}
    return review_indexes == candidate_indexes


def collect_printed_score_recognition_evidence(
    project_dir: Path,
) -> PrintedScoreProductRealityEvidence:
    """Summarize a project's printed-score recognition candidates into sanitized evidence.

    Every registered candidate page must be matched by a review record (the same
    ``page-{NNN}-{sha[:12]}-review.json`` identity ``printed_score_review.create_review_draft``
    writes) with every measure resolved out of ``pending`` before the project can PASS. An
    unreadable/invalid candidate file, or any page still awaiting review, is REVIEW_REQUIRED.
    """

    project_root = Path(project_dir).expanduser().resolve()
    recognition_dir = project_root / PRIVATE_RECOGNITION_RELATIVE_PATH
    candidate_paths = (
        sorted(recognition_dir.glob("*.json")) if recognition_dir.is_dir() else []
    )
    if not candidate_paths:
        raise FileNotFoundError(str(recognition_dir))

    unreadable = 0
    reviewed = 0
    clean_fractions: list[float] = []
    low_confidence_fractions: list[float] = []

    for path in candidate_paths:
        try:
            candidate = PrintedScoreRecognitionCandidateSet.model_validate_json(
                path.read_text(encoding="utf-8")
            )
            candidate_sha256 = sha256_file(path)
        except (OSError, ValueError, ValidationError):
            unreadable += 1
            continue

        metrics = summarize_candidate_set_quality(candidate)
        clean_fractions.append(metrics.clean_measure_fraction)
        low_confidence_fractions.append(metrics.low_confidence_event_fraction)

        review = _matching_review_record(project_root, candidate, candidate_sha256)
        if (
            review is not None
            and review.all_measures_reviewed
            and _review_covers_every_measure(candidate, review)
        ):
            reviewed += 1

    candidate_page_count = len(candidate_paths)
    mean_clean_measure_fraction = (
        sum(clean_fractions) / len(clean_fractions) if clean_fractions else None
    )
    mean_low_confidence_event_fraction = (
        sum(low_confidence_fractions) / len(low_confidence_fractions)
        if low_confidence_fractions
        else None
    )

    if unreadable:
        status: PrintedScoreProductRealityStatus = "REVIEW_REQUIRED"
        message = (
            f"{unreadable} of {candidate_page_count} printed-score recognition candidate "
            "file(s) could not be read or validated."
        )
    elif reviewed == candidate_page_count:
        status = "PASS"
        message = (
            f"All {candidate_page_count} printed-score recognition candidate page(s) "
            "have completed human review."
        )
    else:
        status = "REVIEW_REQUIRED"
        message = (
            f"{candidate_page_count - reviewed} of {candidate_page_count} printed-score "
            "recognition candidate page(s) still require human review before promotion."
        )

    return PrintedScoreProductRealityEvidence(
        status=status,
        candidate_page_count=candidate_page_count,
        reviewed_page_count=reviewed,
        unreadable_candidate_count=unreadable,
        mean_clean_measure_fraction=mean_clean_measure_fraction,
        mean_low_confidence_event_fraction=mean_low_confidence_event_fraction,
        message=message,
    )
