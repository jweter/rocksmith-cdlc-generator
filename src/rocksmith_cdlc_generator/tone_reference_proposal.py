from __future__ import annotations

import hashlib
from pathlib import Path

from pydantic import BaseModel, Field

from .tone_reference_recommendations import (
    RecommendedReferenceComponent,
    ToneRecommendationEvidenceReport,
    ToneReferenceCandidate,
)


class ProposedReferenceComponent(BaseModel):
    slot: str
    device_key: str
    device_name: str | None = None
    device_type: str | None = None
    category: str | None = None
    observed_knob_values: dict[str, float] = Field(default_factory=dict)
    approved: bool = False


class ToneReferenceReviewerProposal(BaseModel):
    schema_version: int = 1
    artist: str
    title: str
    arrangement: str
    arrangement_label: str
    bound_plan_sha256: str
    evidence_sha256: str
    candidate_fingerprint: str
    candidate_source_type: str
    candidate_source_path: str
    candidate_source_psarc_sha256: str
    candidate_tone_key: str
    candidate_tone_name: str | None = None
    selected_components: list[ProposedReferenceComponent] = Field(default_factory=list)
    reviewer_note: str | None = None
    human_review_required: bool = True
    approved: bool = False
    can_auto_apply: bool = False
    can_inject: bool = False


def evidence_digest(report: ToneRecommendationEvidenceReport) -> str:
    """Hash the exact normalized evidence document used for the proposal."""
    payload = report.model_dump_json(exclude_none=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _copy_component(component: RecommendedReferenceComponent) -> ProposedReferenceComponent:
    return ProposedReferenceComponent(
        slot=component.slot,
        device_key=component.device_key,
        device_name=component.device_name,
        device_type=component.device_type,
        category=component.category,
        observed_knob_values=dict(component.knob_values),
        approved=False,
    )


def build_reviewer_proposal(
    report: ToneRecommendationEvidenceReport,
    *,
    arrangement: str,
    candidate_fingerprint: str,
    component_slots: list[str] | None = None,
    reviewer_note: str | None = None,
) -> ToneReferenceReviewerProposal:
    """Stage selected evidence into a separate, explicitly unapproved artifact.

    The returned document never mutates the bound tone plan and cannot represent
    approval or injection readiness. Selection must refer to evidence already
    surfaced in ``report``; arbitrary device keys or knob values cannot be supplied.
    """
    arrangement_evidence = next(
        (item for item in report.arrangements if item.arrangement == arrangement),
        None,
    )
    if arrangement_evidence is None:
        raise ValueError(f"Arrangement {arrangement!r} is not present in the evidence report")

    candidate: ToneReferenceCandidate | None = next(
        (
            item
            for item in arrangement_evidence.candidates
            if item.fingerprint == candidate_fingerprint
        ),
        None,
    )
    if candidate is None:
        raise ValueError("Candidate fingerprint is not present in the selected arrangement evidence")

    requested_slots = None
    if component_slots is not None:
        requested_slots = {slot.casefold() for slot in component_slots}
        if not requested_slots:
            raise ValueError("component_slots must contain at least one slot when supplied")

    selected = [
        component
        for component in candidate.components
        if requested_slots is None or component.slot.casefold() in requested_slots
    ]
    if not selected:
        raise ValueError("No candidate components matched the requested slots")

    if requested_slots is not None:
        found_slots = {component.slot.casefold() for component in selected}
        missing = sorted(requested_slots - found_slots)
        if missing:
            raise ValueError(f"Requested component slots were not found: {', '.join(missing)}")

    return ToneReferenceReviewerProposal(
        artist=report.artist,
        title=report.title,
        arrangement=arrangement_evidence.arrangement,
        arrangement_label=arrangement_evidence.label,
        bound_plan_sha256=report.bound_plan_sha256,
        evidence_sha256=evidence_digest(report),
        candidate_fingerprint=candidate.fingerprint,
        candidate_source_type=str(candidate.source_type),
        candidate_source_path=candidate.source_path,
        candidate_source_psarc_sha256=candidate.source_psarc_sha256,
        candidate_tone_key=candidate.tone_key,
        candidate_tone_name=candidate.tone_name,
        selected_components=[_copy_component(component) for component in selected],
        reviewer_note=reviewer_note,
        human_review_required=True,
        approved=False,
        can_auto_apply=False,
        can_inject=False,
    )


def write_reviewer_proposal(
    proposal: ToneReferenceReviewerProposal,
    destination: Path,
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(proposal.model_dump_json(indent=2), encoding="utf-8")
    return destination
