from __future__ import annotations

from pydantic import BaseModel, Field

from .tone_reference_final_ack import (
    ToneReferenceFinalReviewAcknowledgement,
    staged_diff_digest,
    verify_final_review_acknowledgement,
)
from .tone_reference_review_diff import ToneReviewSettingsDiff, build_staged_settings_diff
from .tone_review import ToneReviewArtifact, approve_component, approve_tone


class GuardedToneApprovalReceipt(BaseModel):
    """Audit receipt for an explicit approval of an acknowledged staged review."""

    schema_version: int = 1
    artist: str
    title: str
    bound_plan_sha256: str
    catalog_sha256: str
    staged_diff_sha256: str
    reviewer: str = Field(min_length=1)
    approved_components: list[str]
    approved_tones: list[str]
    ready_for_injection: bool
    acknowledgement_required: bool = True
    settings_changed_during_approval: bool = False


def _assert_pending_review(artifact: ToneReviewArtifact, *, name: str) -> None:
    if artifact.ready_for_injection:
        raise ValueError(f"{name} tone review is already injection-ready")
    for tone in artifact.tones:
        if tone.decision != "pending":
            raise ValueError(f"{name} tone review contains a non-pending tone: {tone.arrangement}")
        for component in tone.components:
            if component.decision != "pending":
                raise ValueError(
                    f"{name} tone review contains a non-pending component: "
                    f"{tone.arrangement}/{component.family}"
                )


def _verify_exact_current_diff(
    original: ToneReviewArtifact,
    staged: ToneReviewArtifact,
    report: ToneReviewSettingsDiff,
) -> ToneReviewSettingsDiff:
    current = build_staged_settings_diff(original, staged)
    if staged_diff_digest(current) != staged_diff_digest(report):
        raise ValueError("supplied staged settings diff is stale or does not describe the current staged review")
    return current


def approve_acknowledged_staged_review(
    original: ToneReviewArtifact,
    staged: ToneReviewArtifact,
    report: ToneReviewSettingsDiff,
    acknowledgement: ToneReferenceFinalReviewAcknowledgement,
    *,
    reviewer: str,
    confirm_approval: bool,
    reviewer_note: str | None = None,
) -> tuple[ToneReviewArtifact, GuardedToneApprovalReceipt]:
    """Approve exactly the staged values after explicit acknowledgement and confirmation.

    The acknowledgement remains provenance-only. This separate function is the
    explicit approval action. It recomputes the current diff, verifies the
    acknowledgement against that exact diff, and then uses the existing approval
    primitives without allowing device/knob mutation during approval.
    """
    if not confirm_approval:
        raise ValueError("explicit confirm_approval=True is required")

    normalized_reviewer = reviewer.strip()
    if not normalized_reviewer:
        raise ValueError("reviewer must contain a non-whitespace identity")
    if normalized_reviewer != acknowledgement.reviewer:
        raise ValueError("approval reviewer must match the final review acknowledgement reviewer")

    _assert_pending_review(original, name="original")
    _assert_pending_review(staged, name="staged")
    current_report = _verify_exact_current_diff(original, staged, report)
    verify_final_review_acknowledgement(acknowledgement, current_report)

    approved = staged.model_copy(deep=True)
    approved_components: list[str] = []
    approved_tones: list[str] = []

    for tone in staged.tones:
        if not tone.components:
            raise ValueError(f"cannot approve empty tone: {tone.arrangement}")
        for component in tone.components:
            if not component.device_key or not component.slot:
                raise ValueError(
                    f"cannot approve unresolved tone component: {tone.arrangement}/{component.family}"
                )
            approved = approve_component(
                approved,
                arrangement=tone.arrangement,
                family=component.family,
                reviewer_note=reviewer_note,
            )
            approved_components.append(f"{tone.arrangement}/{component.family}")

        approved = approve_tone(
            approved,
            arrangement=tone.arrangement,
            reviewer_note=reviewer_note,
        )
        approved_tones.append(tone.arrangement)

    if not approved.ready_for_injection:
        raise ValueError("guarded approval did not close the injection-ready gate")

    # Approval may only alter review decisions/notes. Device identities and knob
    # values must remain exactly as they were in the acknowledged staged review.
    for before_tone, after_tone in zip(staged.tones, approved.tones, strict=True):
        for before, after in zip(before_tone.components, after_tone.components, strict=True):
            if (
                before.family != after.family
                or before.device_key != after.device_key
                or before.device_name != after.device_name
                or before.slot != after.slot
                or before.knob_values != after.knob_values
            ):
                raise ValueError("tone settings changed during guarded approval")

    receipt = GuardedToneApprovalReceipt(
        artist=approved.artist,
        title=approved.title,
        bound_plan_sha256=approved.bound_plan_sha256,
        catalog_sha256=approved.catalog_sha256,
        staged_diff_sha256=staged_diff_digest(current_report),
        reviewer=normalized_reviewer,
        approved_components=approved_components,
        approved_tones=approved_tones,
        ready_for_injection=True,
        acknowledgement_required=True,
        settings_changed_during_approval=False,
    )
    return approved, receipt
