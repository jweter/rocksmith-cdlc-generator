from __future__ import annotations

import hashlib
from pathlib import Path

from pydantic import BaseModel, Field

from .tone_catalog import BoundRocksmithTonePlan
from .tone_corpus_diagnostics import diagnose_similarity
from .tone_reference_library import ArrangementRole, ReferenceSource, ToneReferenceLibrary


class RecommendedReferenceComponent(BaseModel):
    slot: str
    device_key: str
    device_name: str | None = None
    device_type: str | None = None
    category: str | None = None
    knob_values: dict[str, float] = Field(default_factory=dict)


class ToneReferenceCandidate(BaseModel):
    score: float = Field(ge=0.0)
    authority_weight: float = Field(ge=0.0, le=1.0)
    source_type: ReferenceSource
    source_path: str
    source_psarc_sha256: str
    artist: str | None = None
    title: str | None = None
    tone_key: str
    tone_name: str | None = None
    fingerprint: str
    matched_device_keys: list[str] = Field(default_factory=list)
    descriptors: list[str] = Field(default_factory=list)
    components: list[RecommendedReferenceComponent] = Field(default_factory=list)
    evidence_only: bool = True


class ArrangementReferenceEvidence(BaseModel):
    arrangement: str
    label: str
    query_device_keys: list[str] = Field(default_factory=list)
    candidates: list[ToneReferenceCandidate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    human_review_required: bool = True


class ToneRecommendationEvidenceReport(BaseModel):
    schema_version: int = 1
    artist: str
    title: str
    bound_plan_sha256: str
    library_scan_root: str
    library_psarc_count: int = Field(ge=0)
    library_tone_count: int = Field(ge=0)
    arrangements: list[ArrangementReferenceEvidence] = Field(default_factory=list)
    human_review_required: bool = True
    can_auto_apply: bool = False


def _plan_digest(plan: BoundRocksmithTonePlan) -> str:
    return hashlib.sha256(plan.model_dump_json(exclude_none=False).encode("utf-8")).hexdigest()


def _candidate_from_diagnostic(item) -> ToneReferenceCandidate:
    tone = item.tone
    return ToneReferenceCandidate(
        score=item.score,
        authority_weight=item.authority_weight,
        source_type=tone.source_type,
        source_path=tone.source_path,
        source_psarc_sha256=tone.source_psarc_sha256,
        artist=tone.artist,
        title=tone.title,
        tone_key=tone.tone_key,
        tone_name=tone.tone_name,
        fingerprint=tone.fingerprint,
        matched_device_keys=list(item.matched_device_keys),
        descriptors=list(tone.tone_descriptors),
        components=[
            RecommendedReferenceComponent(
                slot=component.slot,
                device_key=component.device_key,
                device_name=component.device_name,
                device_type=component.device_type,
                category=component.category,
                knob_values=dict(component.knob_values),
            )
            for component in tone.components
        ],
    )


def build_tone_reference_evidence(
    plan: BoundRocksmithTonePlan,
    library: ToneReferenceLibrary,
    *,
    limit_per_arrangement: int = 5,
) -> ToneRecommendationEvidenceReport:
    """Build read-only evidence from the private tone corpus for human review.

    This function deliberately does not modify ``plan`` and exposes no application
    or approval path. A corpus match can inform a reviewer, but it cannot change a
    bound device, copy knob values into the plan, or mark a tone safe for injection.
    """
    if limit_per_arrangement < 1:
        raise ValueError("limit_per_arrangement must be at least 1")

    arrangements: list[ArrangementReferenceEvidence] = []
    supported_roles: set[str] = {"lead", "rhythm", "bass"}
    for tone in plan.tones:
        warnings: list[str] = []
        keys = sorted({
            component.device_key
            for component in tone.components
            if component.device_key
        }, key=str.casefold)

        if tone.arrangement not in supported_roles:
            warnings.append(
                f"Arrangement role {tone.arrangement!r} is not eligible for local reference retrieval."
            )
            arrangements.append(
                ArrangementReferenceEvidence(
                    arrangement=tone.arrangement,
                    label=tone.label,
                    query_device_keys=keys,
                    warnings=warnings,
                )
            )
            continue

        if not keys:
            warnings.append("No resolved Rocksmith device keys are available for reference retrieval.")
            arrangements.append(
                ArrangementReferenceEvidence(
                    arrangement=tone.arrangement,
                    label=tone.label,
                    query_device_keys=[],
                    warnings=warnings,
                )
            )
            continue

        diagnostics = diagnose_similarity(
            library,
            arrangement=tone.arrangement,  # type: ignore[arg-type]
            device_keys=set(keys),
            limit=max(limit_per_arrangement * 4, limit_per_arrangement),
        )

        # A source-authority prior by itself is not enough evidence. Require an
        # actual query-device overlap and collapse duplicate chains so repeated
        # packages cannot crowd out distinct reference choices.
        candidates: list[ToneReferenceCandidate] = []
        seen_fingerprints: set[str] = set()
        for diagnostic in diagnostics:
            if not diagnostic.matched_device_keys:
                continue
            fingerprint = diagnostic.tone.fingerprint
            if fingerprint in seen_fingerprints:
                continue
            seen_fingerprints.add(fingerprint)
            candidates.append(_candidate_from_diagnostic(diagnostic))
            if len(candidates) >= limit_per_arrangement:
                break

        if not candidates:
            warnings.append("No local tone reference shared a resolved device key with this arrangement.")

        arrangements.append(
            ArrangementReferenceEvidence(
                arrangement=tone.arrangement,
                label=tone.label,
                query_device_keys=keys,
                candidates=candidates,
                warnings=warnings,
            )
        )

    return ToneRecommendationEvidenceReport(
        artist=plan.artist,
        title=plan.title,
        bound_plan_sha256=_plan_digest(plan),
        library_scan_root=library.scan_root,
        library_psarc_count=len(library.psarcs),
        library_tone_count=len(library.tones),
        arrangements=arrangements,
        human_review_required=True,
        can_auto_apply=False,
    )


def write_tone_reference_evidence(
    report: ToneRecommendationEvidenceReport,
    destination: Path,
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return destination
