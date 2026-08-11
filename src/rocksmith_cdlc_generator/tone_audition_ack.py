from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .tone_reference_final_ack import staged_diff_digest
from .tone_reference_review_diff import ToneReviewSettingsDiff

AuditionMethod = Literal["live_instrument", "private_di_replay", "external_preview"]
AuditionDecision = Literal["rejected", "keep_editing", "continue_to_review"]


class ToneListeningAcknowledgement(BaseModel):
    """Human listening provenance for one exact staged tone-settings diff."""

    schema_version: int = 1
    artist: str
    title: str
    bound_plan_sha256: str
    catalog_sha256: str
    staged_diff_sha256: str
    reviewer: str = Field(min_length=1)
    audition_method: AuditionMethod
    arrangements: list[str] = Field(min_length=1)
    decision: AuditionDecision
    reviewer_note: str | None = None
    human_listening_confirmed: bool = True
    can_approve: bool = False
    can_inject: bool = False

    @model_validator(mode="after")
    def validate_arrangements(self) -> "ToneListeningAcknowledgement":
        normalized = [value.strip() for value in self.arrangements]
        if any(not value for value in normalized):
            raise ValueError("listening acknowledgement arrangements cannot be blank")
        folded = [value.casefold() for value in normalized]
        if len(folded) != len(set(folded)):
            raise ValueError("listening acknowledgement arrangements must be unique")
        self.arrangements = normalized
        return self


def acknowledge_tone_listening(
    report: ToneReviewSettingsDiff,
    *,
    reviewer: str,
    audition_method: AuditionMethod,
    arrangements: list[str],
    decision: AuditionDecision,
    reviewer_note: str | None = None,
) -> ToneListeningAcknowledgement:
    """Record that a human listened to settings represented by one exact diff.

    Listening remains non-approving. A later approval gate may require a
    `continue_to_review` acknowledgement, but this artifact alone cannot approve or
    inject anything.
    """
    if not report.human_review_required:
        raise ValueError("staged settings diff must require human review")
    if report.can_approve or report.can_inject:
        raise ValueError("staged settings diff safety flags prohibit approval and injection")

    normalized_reviewer = reviewer.strip()
    if not normalized_reviewer:
        raise ValueError("reviewer must contain a non-whitespace identity")

    return ToneListeningAcknowledgement(
        artist=report.artist,
        title=report.title,
        bound_plan_sha256=report.bound_plan_sha256,
        catalog_sha256=report.catalog_sha256,
        staged_diff_sha256=staged_diff_digest(report),
        reviewer=normalized_reviewer,
        audition_method=audition_method,
        arrangements=arrangements,
        decision=decision,
        reviewer_note=reviewer_note,
        human_listening_confirmed=True,
        can_approve=False,
        can_inject=False,
    )


def verify_tone_listening_acknowledgement(
    acknowledgement: ToneListeningAcknowledgement,
    report: ToneReviewSettingsDiff,
    *,
    require_continue_to_review: bool = False,
) -> None:
    """Fail closed unless listening provenance matches the exact current diff."""
    if not report.human_review_required:
        raise ValueError("staged settings diff must require human review")
    if report.can_approve or report.can_inject:
        raise ValueError("staged settings diff safety flags prohibit approval and injection")
    if not acknowledgement.human_listening_confirmed:
        raise ValueError("listening acknowledgement must confirm human listening")
    if acknowledgement.can_approve or acknowledgement.can_inject:
        raise ValueError("listening acknowledgement cannot grant approval or injection")
    if acknowledgement.artist != report.artist or acknowledgement.title != report.title:
        raise ValueError("listening acknowledgement identifies a different song")
    if acknowledgement.bound_plan_sha256 != report.bound_plan_sha256:
        raise ValueError("listening acknowledgement references a different bound plan")
    if acknowledgement.catalog_sha256 != report.catalog_sha256:
        raise ValueError("listening acknowledgement references a different tone catalog")
    if acknowledgement.staged_diff_sha256 != staged_diff_digest(report):
        raise ValueError("listening acknowledgement was created from a different staged settings diff")
    if require_continue_to_review and acknowledgement.decision != "continue_to_review":
        raise ValueError("listening decision must be continue_to_review before final approval")


def write_tone_listening_acknowledgement(
    acknowledgement: ToneListeningAcknowledgement,
    destination: Path,
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(acknowledgement.model_dump_json(indent=2), encoding="utf-8")
    return destination
