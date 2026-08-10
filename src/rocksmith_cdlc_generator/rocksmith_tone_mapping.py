from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .tone_research import ArrangementRole, EffectCandidate, ToneRigHypothesis

ToneSlot = Literal["base", "tone_a", "tone_b", "tone_c", "tone_d"]
ComponentFamily = Literal[
    "amp_clean",
    "amp_crunch",
    "amp_high_gain",
    "amp_fuzz",
    "compressor",
    "boost",
    "overdrive",
    "distortion",
    "fuzz",
    "wah_filter",
    "chorus",
    "flanger",
    "phaser",
    "tremolo",
    "vibrato",
    "rotary",
    "delay",
    "reverb",
    "octave_pitch",
    "noise_gate",
    "eq",
]


class ToneComponentSuggestion(BaseModel):
    family: ComponentFamily
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_urls: list[str] = Field(default_factory=list)
    exact_model_known: bool = False


class RocksmithToneSuggestion(BaseModel):
    slot: ToneSlot
    arrangement: ArrangementRole
    label: str
    tone_family: str
    confidence: float = Field(ge=0.0, le=1.0)
    components: list[ToneComponentSuggestion]
    review_required: bool = True
    warnings: list[str] = Field(default_factory=list)


class RocksmithTonePlan(BaseModel):
    schema_version: int = 1
    artist: str
    title: str
    tones: list[RocksmithToneSuggestion]
    source_evidence_count: int = Field(ge=0)
    safe_for_automatic_injection: bool = False
    warnings: list[str] = Field(default_factory=list)


_EFFECT_COMPONENT: dict[str, ComponentFamily] = {
    "compression": "compressor",
    "boost": "boost",
    "overdrive": "overdrive",
    "distortion": "distortion",
    "fuzz": "fuzz",
    "wah_filter": "wah_filter",
    "chorus": "chorus",
    "flanger": "flanger",
    "phaser": "phaser",
    "tremolo": "tremolo",
    "vibrato": "vibrato",
    "rotary": "rotary",
    "delay": "delay",
    "reverb": "reverb",
    "octave_pitch": "octave_pitch",
    "noise_gate": "noise_gate",
    "eq": "eq",
}

_AMP_COMPONENT: dict[str, ComponentFamily] = {
    "clean": "amp_clean",
    "edge_of_breakup": "amp_crunch",
    "crunch": "amp_crunch",
    "high_gain": "amp_high_gain",
    "fuzz": "amp_fuzz",
    "acoustic_like": "amp_clean",
    "unknown": "amp_clean",
}


def _candidate_confidence(candidate: EffectCandidate) -> float:
    # Support scores are additive across evidence, so convert them to a bounded confidence.
    return round(min(0.98, 0.45 + candidate.support_score / (candidate.support_score + 1.5) * 0.53), 4)


def _tone_family(hypothesis: ToneRigHypothesis) -> tuple[str, float]:
    if not hypothesis.tone_families:
        return "unknown", 0.35
    family, probability = max(hypothesis.tone_families.items(), key=lambda item: item[1])
    return family, max(0.35, min(0.98, float(probability)))


def _effects_for_role(hypothesis: ToneRigHypothesis, role: ArrangementRole) -> list[EffectCandidate]:
    candidates = [item for item in hypothesis.effects if item.arrangement in {None, role}]
    # Keep the strongest claim per family for a compact, reviewable signal chain.
    strongest: dict[str, EffectCandidate] = {}
    for item in candidates:
        current = strongest.get(item.family)
        if current is None or item.support_score > current.support_score:
            strongest[item.family] = item
    return sorted(strongest.values(), key=lambda item: (-item.support_score, item.family))


def map_tone_hypothesis(
    hypothesis: ToneRigHypothesis,
    *,
    arrangements: list[ArrangementRole],
    minimum_effect_support: float = 0.35,
) -> RocksmithTonePlan:
    """Convert researched rig/effect evidence into a conservative Rocksmith tone plan.

    This deliberately maps to component *families*, not undocumented DLC Builder
    component identifiers. A later catalog-binding step must select exact Rocksmith
    devices from a pinned authoritative catalog before any .rs2dlc injection occurs.
    """
    if not arrangements:
        raise ValueError("at least one arrangement is required for tone mapping")
    if minimum_effect_support < 0:
        raise ValueError("minimum_effect_support must be non-negative")

    family, family_confidence = _tone_family(hypothesis)
    tones: list[RocksmithToneSuggestion] = []
    plan_warnings = list(hypothesis.warnings)

    for role in arrangements:
        components: list[ToneComponentSuggestion] = [
            ToneComponentSuggestion(
                family=_AMP_COMPONENT.get(family, "amp_clean"),
                reason=f"Dominant researched tone family: {family}.",
                confidence=family_confidence,
            )
        ]
        role_effects = [
            effect for effect in _effects_for_role(hypothesis, role)
            if effect.support_score >= minimum_effect_support and effect.family in _EFFECT_COMPONENT
        ]
        for effect in role_effects:
            components.append(
                ToneComponentSuggestion(
                    family=_EFFECT_COMPONENT[effect.family],
                    reason=f"Research evidence supports {effect.family} for {role}.",
                    confidence=_candidate_confidence(effect),
                    evidence_urls=effect.evidence_urls,
                )
            )

        warnings: list[str] = []
        if family == "unknown":
            warnings.append("No reliable dominant amp/tone family has been established.")
        if not role_effects:
            warnings.append("No effect family met the support threshold; review the dry/base tone manually.")
        if hypothesis.evidence_count == 0:
            warnings.append("Tone plan has no external research evidence.")

        component_confidence = min(component.confidence for component in components)
        tones.append(
            RocksmithToneSuggestion(
                slot="base",
                arrangement=role,
                label=f"{role.capitalize()} Base",
                tone_family=family,
                confidence=round(component_confidence, 4),
                components=components,
                review_required=True,
                warnings=warnings,
            )
        )

    if hypothesis.evidence_count == 0:
        plan_warnings.append("Automatic Rocksmith tone selection is not justified without evidence.")
    plan_warnings.append(
        "Exact Rocksmith device identifiers and parameter values are intentionally unresolved until an authoritative component catalog is pinned."
    )
    return RocksmithTonePlan(
        artist=hypothesis.song.artist,
        title=hypothesis.song.title,
        tones=tones,
        source_evidence_count=hypothesis.evidence_count,
        safe_for_automatic_injection=False,
        warnings=plan_warnings,
    )
