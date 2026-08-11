from __future__ import annotations

from pydantic import BaseModel, Field

from .tone_reference_audition_ack import (
    ToneAuditionAcknowledgement,
    verify_tone_audition_acknowledgement,
)
from .tone_reference_final_ack import (
    ToneReferenceFinalReviewAcknowledgement,
    verify_final_review_acknowledgement,
)
from .tone_reference_review_diff import (
    ToneReviewSettingsDiff,
    build_staged_settings_diff,
)
from .tone_review import ToneReviewArtifact, approve_component, approve_tone


class ComponentApprovalRequest(BaseModel):
    arrangement: str = Field(min_length=1)
    family: str = Field(min_length=1)
    reviewer_note: str | None = None


class ToneApprovalRequest(BaseModel):
    arrangement: str = Field(min_length=1)
    reviewer_note: str | None = None


class GuardedToneApprovalRequest(BaseModel):
    """Explicit human approval actions to execute after provenance validation."""

    component_approvals: list[ComponentApprovalRequest] = Field(default_factory=list)
    tone_approvals: list[ToneApprovalRequest] = Field(default_factory=list)


class ToneApprovalPolicy(BaseModel):
    """Policy gates that may be required before explicit approval actions execute."""

    require_current_audition: bool = False


def _assert_unique_actions(request: GuardedToneApprovalRequest) -> None:
    component_keys = [
        (item.arrangement.casefold(), item.family.casefold())
        for item in request.component_approvals
    ]
    if len(component_keys) != len(set(component_keys)):
        raise ValueError("duplicate component approval actions are not allowed")

    tone_keys = [item.arrangement.casefold() for item in request.tone_approvals]
    if len(tone_keys) != len(set(tone_keys)):
        raise ValueError("duplicate tone approval actions are not allowed")

    if not request.component_approvals and not request.tone_approvals:
        raise ValueError("at least one explicit approval action is required")


def guarded_final_tone_approval(
    original_review: ToneReviewArtifact,
    staged_review: ToneReviewArtifact,
    acknowledged_diff: ToneReviewSettingsDiff,
    acknowledgement: ToneReferenceFinalReviewAcknowledgement,
    request: GuardedToneApprovalRequest,
    *,
    policy: ToneApprovalPolicy | None = None,
    audition_acknowledgement: ToneAuditionAcknowledgement | None = None,
) -> ToneReviewArtifact:
    """Execute explicit approvals only after validating all configured human gates.

    The staged-vs-original comparison is recomputed at call time. Any setting change
    invalidates the reviewed diff. When policy requires audition, approval additionally
    requires a current acknowledgement for that exact diff whose human listening result
    is ``sounds_right``. Neither acknowledgement can alter settings or approve anything
    on its own.
    """
    _assert_unique_actions(request)

    current_diff = build_staged_settings_diff(original_review, staged_review)
    if current_diff.model_dump(exclude_none=False) != acknowledged_diff.model_dump(exclude_none=False):
        raise ValueError(
            "current staged settings do not match the acknowledged diff; regenerate and review the diff"
        )

    verify_final_review_acknowledgement(acknowledgement, current_diff)

    effective_policy = policy or ToneApprovalPolicy()
    if effective_policy.require_current_audition:
        if audition_acknowledgement is None:
            raise ValueError("current tone audition acknowledgement is required by approval policy")
        verify_tone_audition_acknowledgement(audition_acknowledgement, current_diff)
        if audition_acknowledgement.decision != "sounds_right":
            raise ValueError("tone audition requires revision; final approval is blocked")

    result = staged_review.model_copy(deep=True)
    for item in request.component_approvals:
        result = approve_component(
            result,
            arrangement=item.arrangement,
            family=item.family,
            reviewer_note=item.reviewer_note,
        )

    for item in request.tone_approvals:
        result = approve_tone(
            result,
            arrangement=item.arrangement,
            reviewer_note=item.reviewer_note,
        )

    return result
