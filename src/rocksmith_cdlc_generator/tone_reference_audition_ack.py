from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .tone_reference_review_diff import ToneReviewSettingsDiff

AuditionDecision = Literal["sounds_right", "needs_revision"]


class ToneAuditionAcknowledgement(BaseModel):
    schema_version: int = 1
    artist: str
    title: str
    bound_plan_sha256: str
    catalog_sha256: str
    staged_diff_sha256: str
    reviewer: str = Field(min_length=1)
    decision: AuditionDecision
    audition_method: str = Field(min_length=1)
    reviewer_note: str | None = None
    human_listening_confirmed: bool = True
    can_approve: bool = False
    can_inject: bool = False


def staged_diff_digest(report: ToneReviewSettingsDiff) -> str:
    payload = report.model_dump_json(exclude_none=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def acknowledge_tone_audition(
    report: ToneReviewSettingsDiff,
    *,
    reviewer: str,
    decision: AuditionDecision,
    audition_method: str,
    reviewer_note: str | None = None,
) -> ToneAuditionAcknowledgement:
    if not report.human_review_required or report.can_approve or report.can_inject:
        raise ValueError("staged settings diff is not valid for human audition acknowledgement")
    reviewer = reviewer.strip()
    audition_method = audition_method.strip()
    if not reviewer:
        raise ValueError("reviewer must contain a non-whitespace identity")
    if not audition_method:
        raise ValueError("audition_method must describe how the tone was heard")
    return ToneAuditionAcknowledgement(
        artist=report.artist,
        title=report.title,
        bound_plan_sha256=report.bound_plan_sha256,
        catalog_sha256=report.catalog_sha256,
        staged_diff_sha256=staged_diff_digest(report),
        reviewer=reviewer,
        decision=decision,
        audition_method=audition_method,
        reviewer_note=reviewer_note,
        human_listening_confirmed=True,
        can_approve=False,
        can_inject=False,
    )


def verify_tone_audition_acknowledgement(
    acknowledgement: ToneAuditionAcknowledgement,
    report: ToneReviewSettingsDiff,
) -> None:
    if not acknowledgement.human_listening_confirmed:
        raise ValueError("audition acknowledgement must confirm human listening")
    if acknowledgement.can_approve or acknowledgement.can_inject:
        raise ValueError("audition acknowledgement cannot grant approval or injection")
    if acknowledgement.artist != report.artist or acknowledgement.title != report.title:
        raise ValueError("audition acknowledgement identifies a different song")
    if acknowledgement.bound_plan_sha256 != report.bound_plan_sha256:
        raise ValueError("audition acknowledgement references a different bound plan")
    if acknowledgement.catalog_sha256 != report.catalog_sha256:
        raise ValueError("audition acknowledgement references a different tone catalog")
    if acknowledgement.staged_diff_sha256 != staged_diff_digest(report):
        raise ValueError("audition acknowledgement was created from a different staged settings diff")


def write_tone_audition_acknowledgement(
    acknowledgement: ToneAuditionAcknowledgement,
    destination: Path,
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(acknowledgement.model_dump_json(indent=2), encoding="utf-8")
    return destination
