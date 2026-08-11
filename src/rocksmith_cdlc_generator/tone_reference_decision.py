from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .tone_reference_proposal import ToneReferenceReviewerProposal
from .tone_review import ToneReviewArtifact

ProposalDecision = Literal["accepted", "rejected"]


class ToneReferenceComponentDecision(BaseModel):
    slot: str
    decision: ProposalDecision
    reviewer_note: str | None = None


class ToneReferenceReviewDecision(BaseModel):
    schema_version: int = 1
    artist: str
    title: str
    arrangement: str
    bound_plan_sha256: str
    proposal_sha256: str
    decisions: list[ToneReferenceComponentDecision] = Field(default_factory=list)
    human_review_confirmed: bool = True
    can_auto_apply: bool = False
    can_inject: bool = False


def proposal_digest(proposal: ToneReferenceReviewerProposal) -> str:
    payload = proposal.model_dump_json(exclude_none=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _assert_proposal_is_review_only(proposal: ToneReferenceReviewerProposal) -> None:
    if not proposal.human_review_required:
        raise ValueError("proposal must require human review")
    if proposal.approved or proposal.can_auto_apply or proposal.can_inject:
        raise ValueError("proposal safety flags are invalid for review staging")


def build_review_decision(
    proposal: ToneReferenceReviewerProposal,
    *,
    accept_slots: list[str] | None = None,
    reject_slots: list[str] | None = None,
    reviewer_note: str | None = None,
) -> ToneReferenceReviewDecision:
    """Record an explicit human accept/reject decision for every proposed slot.

    Acceptance here means only "stage this observed reference into the existing
    tone-review artifact." It is not component approval and cannot make a tone
    injection-ready.
    """
    _assert_proposal_is_review_only(proposal)
    proposed = {component.slot.casefold(): component.slot for component in proposal.selected_components}
    if len(proposed) != len(proposal.selected_components):
        raise ValueError("proposal contains duplicate component slots")
    if not proposed:
        raise ValueError("proposal contains no components to review")

    accepted = {slot.casefold() for slot in (accept_slots or [])}
    rejected = {slot.casefold() for slot in (reject_slots or [])}
    overlap = sorted(accepted & rejected)
    if overlap:
        raise ValueError("component slots cannot be both accepted and rejected: " + ", ".join(overlap))

    requested = accepted | rejected
    unknown = sorted(requested - set(proposed))
    if unknown:
        raise ValueError("decision references component slots not present in proposal: " + ", ".join(unknown))

    missing = sorted(set(proposed) - requested)
    if missing:
        raise ValueError("every proposed component requires an explicit decision; missing: " + ", ".join(missing))

    decisions = [
        ToneReferenceComponentDecision(
            slot=proposed[key],
            decision="accepted" if key in accepted else "rejected",
            reviewer_note=reviewer_note,
        )
        for key in sorted(proposed)
    ]
    return ToneReferenceReviewDecision(
        artist=proposal.artist,
        title=proposal.title,
        arrangement=proposal.arrangement,
        bound_plan_sha256=proposal.bound_plan_sha256,
        proposal_sha256=proposal_digest(proposal),
        decisions=decisions,
        human_review_confirmed=True,
        can_auto_apply=False,
        can_inject=False,
    )


def stage_accepted_components(
    review: ToneReviewArtifact,
    proposal: ToneReferenceReviewerProposal,
    decision: ToneReferenceReviewDecision,
) -> ToneReviewArtifact:
    """Stage explicitly accepted reference observations into a pending tone review.

    The bound plan is never changed. Staged components stay ``pending`` and the
    resulting review remains not ready for injection until the existing human
    approval workflow is completed separately.
    """
    _assert_proposal_is_review_only(proposal)
    if not decision.human_review_confirmed:
        raise ValueError("decision must record explicit human review")
    if decision.can_auto_apply or decision.can_inject:
        raise ValueError("decision safety flags prohibit automatic apply and injection")
    if review.bound_plan_sha256 != proposal.bound_plan_sha256:
        raise ValueError("proposal was created from a different bound tone plan")
    if decision.bound_plan_sha256 != proposal.bound_plan_sha256:
        raise ValueError("decision bound-plan SHA-256 does not match proposal")
    if decision.proposal_sha256 != proposal_digest(proposal):
        raise ValueError("decision was created from a different reviewer proposal")
    if decision.arrangement != proposal.arrangement:
        raise ValueError("decision arrangement does not match proposal")
    if review.ready_for_injection:
        raise ValueError("cannot stage reference evidence into an injection-ready tone review")

    proposal_by_slot = {component.slot.casefold(): component for component in proposal.selected_components}
    if len(proposal_by_slot) != len(proposal.selected_components):
        raise ValueError("proposal contains duplicate component slots")
    decision_by_slot = {item.slot.casefold(): item for item in decision.decisions}
    if len(decision_by_slot) != len(decision.decisions):
        raise ValueError("decision contains duplicate component slots")
    if set(decision_by_slot) != set(proposal_by_slot):
        raise ValueError("decision must cover exactly the component slots in the proposal")

    data = review.model_dump()
    tones = [tone for tone in data["tones"] if tone["arrangement"] == proposal.arrangement]
    if len(tones) != 1:
        raise ValueError("tone review must contain exactly one matching arrangement")
    tone = tones[0]
    if tone["decision"] != "pending":
        raise ValueError("reference evidence may only be staged into a pending tone review")

    for slot_key, item in decision_by_slot.items():
        if item.decision != "accepted":
            continue
        observed = proposal_by_slot[slot_key]
        matches = [
            component
            for component in tone["components"]
            if component.get("slot") and component["slot"].casefold() == slot_key
        ]
        if len(matches) != 1:
            raise ValueError(f"pending tone review must contain exactly one component in slot {observed.slot!r}")
        target = matches[0]
        if target["decision"] != "pending":
            raise ValueError(f"reference evidence may only replace a pending component: {observed.slot}")
        target["device_key"] = observed.device_key
        target["device_name"] = observed.device_name
        target["knob_values"] = dict(observed.observed_knob_values)
        note = "Accepted local reference evidence staged; final component approval is still required."
        if item.reviewer_note:
            note += f" Reviewer note: {item.reviewer_note}"
        target["reviewer_note"] = note
        target["decision"] = "pending"

    data["ready_for_injection"] = False
    return ToneReviewArtifact.model_validate(data)


def write_review_decision(decision: ToneReferenceReviewDecision, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(decision.model_dump_json(indent=2), encoding="utf-8")
    return destination
