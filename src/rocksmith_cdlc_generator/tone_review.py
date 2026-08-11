from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .tone_catalog import BoundRocksmithTonePlan, BoundToneComponent

ReviewDecision = Literal["pending", "approved", "rejected"]


class ToneComponentReview(BaseModel):
    family: str
    device_key: str | None = None
    device_name: str | None = None
    slot: str | None = None
    knob_values: dict[str, float] = Field(default_factory=dict)
    decision: ReviewDecision = "pending"
    reviewer_note: str | None = None


class ToneReviewItem(BaseModel):
    arrangement: str
    label: str
    components: list[ToneComponentReview]
    decision: ReviewDecision = "pending"
    reviewer_note: str | None = None

    @model_validator(mode="after")
    def approval_requires_components(self) -> "ToneReviewItem":
        if self.decision == "approved":
            if not self.components:
                raise ValueError("approved tone must contain at least one component")
            unresolved = [item.family for item in self.components if item.decision != "approved"]
            if unresolved:
                raise ValueError(
                    "approved tone requires every component to be approved; unresolved: "
                    + ", ".join(unresolved)
                )
        return self


class ToneReviewArtifact(BaseModel):
    schema_version: int = 1
    artist: str
    title: str
    catalog_sha256: str
    bound_plan_sha256: str
    tones: list[ToneReviewItem]
    ready_for_injection: bool = False

    @model_validator(mode="after")
    def ready_only_when_fully_approved(self) -> "ToneReviewArtifact":
        approved = bool(self.tones) and all(tone.decision == "approved" for tone in self.tones)
        if self.ready_for_injection != approved:
            raise ValueError("ready_for_injection must exactly reflect full human approval")
        return self


def _plan_digest(plan: BoundRocksmithTonePlan) -> str:
    payload = plan.model_dump_json(exclude_none=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def create_tone_review(plan: BoundRocksmithTonePlan) -> ToneReviewArtifact:
    tones: list[ToneReviewItem] = []
    for tone in plan.tones:
        components = [
            ToneComponentReview(
                family=component.family,
                device_key=component.device_key,
                device_name=component.device_name,
                slot=component.slot,
                knob_values=dict(component.knob_values),
            )
            for component in tone.components
        ]
        tones.append(ToneReviewItem(arrangement=tone.arrangement, label=tone.label, components=components))
    return ToneReviewArtifact(
        artist=plan.artist,
        title=plan.title,
        catalog_sha256=plan.catalog_sha256,
        bound_plan_sha256=_plan_digest(plan),
        tones=tones,
        ready_for_injection=False,
    )


def approve_component(
    artifact: ToneReviewArtifact,
    *,
    arrangement: str,
    family: str,
    knob_values: dict[str, float] | None = None,
    reviewer_note: str | None = None,
) -> ToneReviewArtifact:
    data = artifact.model_dump()
    found = False
    for tone in data["tones"]:
        if tone["arrangement"] != arrangement:
            continue
        for component in tone["components"]:
            if component["family"] != family:
                continue
            if not component.get("device_key") or not component.get("slot"):
                raise ValueError(f"cannot approve unresolved tone component: {arrangement}/{family}")
            component["decision"] = "approved"
            if knob_values is not None:
                component["knob_values"] = knob_values
            component["reviewer_note"] = reviewer_note
            found = True
    if not found:
        raise ValueError(f"tone component not found: {arrangement}/{family}")
    return ToneReviewArtifact.model_validate(data)


def approve_tone(
    artifact: ToneReviewArtifact,
    *,
    arrangement: str,
    reviewer_note: str | None = None,
) -> ToneReviewArtifact:
    data = artifact.model_dump()
    found = False
    for tone in data["tones"]:
        if tone["arrangement"] == arrangement:
            if any(component["decision"] != "approved" for component in tone["components"]):
                raise ValueError("all tone components must be approved before approving the tone")
            tone["decision"] = "approved"
            tone["reviewer_note"] = reviewer_note
            found = True
    if not found:
        raise ValueError(f"tone not found: {arrangement}")
    data["ready_for_injection"] = bool(data["tones"]) and all(
        tone["decision"] == "approved" for tone in data["tones"]
    )
    return ToneReviewArtifact.model_validate(data)


def verify_review_matches_plan(artifact: ToneReviewArtifact, plan: BoundRocksmithTonePlan) -> None:
    if artifact.catalog_sha256 != plan.catalog_sha256:
        raise ValueError("tone review catalog SHA-256 does not match current bound tone plan")
    if artifact.bound_plan_sha256 != _plan_digest(plan):
        raise ValueError("tone review was created from a different bound tone plan")


def write_tone_review(artifact: ToneReviewArtifact, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")
    return destination


def load_tone_review(path: Path) -> ToneReviewArtifact:
    return ToneReviewArtifact.model_validate_json(path.read_text(encoding="utf-8"))
