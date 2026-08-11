from __future__ import annotations

import hashlib
from pathlib import Path

from pydantic import BaseModel, Field

from .tone_reference_review_diff import ToneReviewSettingsDiff


class ToneReferenceFinalReviewAcknowledgement(BaseModel):
    """Human acknowledgement of one exact staged-settings diff.

    This artifact records that a reviewer inspected the comparison. It does not
    approve any component or tone and cannot close the injection gate.
    """

    schema_version: int = 1
    artist: str
    title: str
    bound_plan_sha256: str
    catalog_sha256: str
    staged_diff_sha256: str
    reviewer: str = Field(min_length=1)
    reviewer_note: str | None = None
    human_review_confirmed: bool = True
    can_approve: bool = False
    can_inject: bool = False


def staged_diff_digest(report: ToneReviewSettingsDiff) -> str:
    """Return a deterministic SHA-256 for the normalized diff document."""
    payload = report.model_dump_json(exclude_none=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _assert_review_only_diff(report: ToneReviewSettingsDiff) -> None:
    if not report.human_review_required:
        raise ValueError("staged settings diff must require human review")
    if report.can_approve or report.can_inject:
        raise ValueError("staged settings diff safety flags prohibit approval and injection")


def acknowledge_staged_settings_diff(
    report: ToneReviewSettingsDiff,
    *,
    reviewer: str,
    reviewer_note: str | None = None,
) -> ToneReferenceFinalReviewAcknowledgement:
    """Acknowledge inspection of one exact staged-settings diff.

    The acknowledgement is provenance only. It cannot change the underlying tone
    review or represent component/tone approval.
    """
    _assert_review_only_diff(report)
    normalized_reviewer = reviewer.strip()
    if not normalized_reviewer:
        raise ValueError("reviewer must contain a non-whitespace identity")

    return ToneReferenceFinalReviewAcknowledgement(
        artist=report.artist,
        title=report.title,
        bound_plan_sha256=report.bound_plan_sha256,
        catalog_sha256=report.catalog_sha256,
        staged_diff_sha256=staged_diff_digest(report),
        reviewer=normalized_reviewer,
        reviewer_note=reviewer_note,
        human_review_confirmed=True,
        can_approve=False,
        can_inject=False,
    )


def verify_final_review_acknowledgement(
    acknowledgement: ToneReferenceFinalReviewAcknowledgement,
    report: ToneReviewSettingsDiff,
) -> None:
    """Fail closed unless an acknowledgement matches the exact current diff."""
    _assert_review_only_diff(report)
    if not acknowledgement.human_review_confirmed:
        raise ValueError("final review acknowledgement must confirm human review")
    if acknowledgement.can_approve or acknowledgement.can_inject:
        raise ValueError("final review acknowledgement cannot grant approval or injection")
    if acknowledgement.artist != report.artist or acknowledgement.title != report.title:
        raise ValueError("final review acknowledgement identifies a different song")
    if acknowledgement.bound_plan_sha256 != report.bound_plan_sha256:
        raise ValueError("final review acknowledgement references a different bound plan")
    if acknowledgement.catalog_sha256 != report.catalog_sha256:
        raise ValueError("final review acknowledgement references a different tone catalog")
    if acknowledgement.staged_diff_sha256 != staged_diff_digest(report):
        raise ValueError("final review acknowledgement was created from a different staged settings diff")


def write_final_review_acknowledgement(
    acknowledgement: ToneReferenceFinalReviewAcknowledgement,
    destination: Path,
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(acknowledgement.model_dump_json(indent=2), encoding="utf-8")
    return destination
