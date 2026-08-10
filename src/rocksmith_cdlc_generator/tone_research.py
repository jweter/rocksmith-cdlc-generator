from __future__ import annotations

from collections import defaultdict
from typing import Literal
from urllib.parse import quote_plus, urlparse

from pydantic import BaseModel, Field, model_validator

ArrangementRole = Literal["lead", "rhythm", "bass"]
EvidenceScope = Literal["track", "album", "era", "artist"]
EvidenceKind = Literal[
    "artist_interview",
    "producer_interview",
    "studio_feature",
    "rig_rundown",
    "equipboard_submission",
    "manufacturer_artist_page",
    "secondary_article",
    "community_post",
]
EffectFamily = Literal[
    "compression", "boost", "overdrive", "distortion", "fuzz", "wah_filter",
    "chorus", "flanger", "phaser", "tremolo", "vibrato", "rotary",
    "delay", "reverb", "octave_pitch", "noise_gate", "eq", "other",
]
ToneFamily = Literal[
    "clean", "edge_of_breakup", "crunch", "high_gain", "fuzz", "acoustic_like", "unknown",
]

_SOURCE_WEIGHT: dict[EvidenceKind, float] = {
    "artist_interview": 1.00,
    "producer_interview": 1.00,
    "studio_feature": 0.94,
    "rig_rundown": 0.90,
    "manufacturer_artist_page": 0.82,
    "equipboard_submission": 0.78,
    "secondary_article": 0.68,
    "community_post": 0.42,
}
_SCOPE_WEIGHT: dict[EvidenceScope, float] = {
    "track": 1.00,
    "album": 0.88,
    "era": 0.70,
    "artist": 0.52,
}


class SongIdentity(BaseModel):
    artist: str = Field(min_length=1)
    title: str = Field(min_length=1)
    album: str | None = None
    year: int | None = Field(default=None, ge=1900, le=2200)


class ResearchQuery(BaseModel):
    label: str
    query: str
    rationale: str
    preferred_domains: list[str] = Field(default_factory=list)

    @property
    def search_url(self) -> str:
        return f"https://www.google.com/search?q={quote_plus(self.query)}"


class ToneResearchPlan(BaseModel):
    schema_version: int = 1
    song: SongIdentity
    queries: list[ResearchQuery]


class GearClaim(BaseModel):
    category: Literal["guitar", "bass", "amp", "cab", "pedal", "rack", "plugin", "studio", "other"]
    model: str = Field(min_length=1)
    manufacturer: str | None = None
    usage: str | None = None
    arrangement: ArrangementRole | None = None


class EffectClaim(BaseModel):
    family: EffectFamily
    detail: str | None = None
    arrangement: ArrangementRole | None = None


class ToneEvidence(BaseModel):
    schema_version: int = 1
    url: str
    title: str = Field(min_length=1)
    publisher: str | None = None
    kind: EvidenceKind
    scope: EvidenceScope
    basis: str = Field(min_length=1)
    gear: list[GearClaim] = Field(default_factory=list)
    effects: list[EffectClaim] = Field(default_factory=list)
    tone_family: ToneFamily | None = None
    arrangement: ArrangementRole | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    notes: str | None = None

    @model_validator(mode="after")
    def valid_source_url(self) -> "ToneEvidence":
        parsed = urlparse(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("tone evidence URL must be an absolute HTTP(S) URL")
        return self

    @property
    def authority_score(self) -> float:
        return round(_SOURCE_WEIGHT[self.kind] * _SCOPE_WEIGHT[self.scope] * self.confidence, 4)


class GearCandidate(BaseModel):
    category: str
    model: str
    manufacturer: str | None = None
    arrangement: ArrangementRole | None = None
    support_score: float = Field(ge=0.0)
    evidence_urls: list[str]


class EffectCandidate(BaseModel):
    family: EffectFamily
    arrangement: ArrangementRole | None = None
    support_score: float = Field(ge=0.0)
    evidence_urls: list[str]


class ToneRigHypothesis(BaseModel):
    schema_version: int = 1
    song: SongIdentity
    gear: list[GearCandidate]
    effects: list[EffectCandidate]
    tone_families: dict[str, float]
    evidence_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


def build_tone_research_plan(song: SongIdentity) -> ToneResearchPlan:
    artist, title = song.artist, song.title
    queries = [
        ResearchQuery(
            label="track-specific gear",
            query=f'"{artist}" "{title}" guitar gear amp pedals recording',
            rationale="Find track-specific rig/session evidence.",
            preferred_domains=["equipboard.com", "premierguitar.com", "guitarworld.com", "musicradar.com"],
        ),
        ResearchQuery(
            label="direct artist evidence",
            query=f'"{artist}" "{title}" interview guitar tone amp pedal recording',
            rationale="Direct musician statements are high-authority evidence.",
            preferred_domains=["guitarworld.com", "musicradar.com", "premierguitar.com"],
        ),
        ResearchQuery(
            label="rig rundown",
            query=f'"{artist}" rig rundown guitar amp pedals',
            rationale="Establish the documented rig near the recording era.",
            preferred_domains=["premierguitar.com"],
        ),
        ResearchQuery(
            label="Equipboard evidence",
            query=f'site:equipboard.com/pros "{artist}" guitar amp pedal',
            rationale="Find source-backed artist gear submissions and album tags.",
            preferred_domains=["equipboard.com"],
        ),
    ]
    if song.album:
        queries.extend([
            ResearchQuery(
                label="album-specific gear",
                query=f'"{artist}" "{song.album}" guitar gear recording amp pedals',
                rationale="Album-session evidence constrains the rig used on the track.",
                preferred_domains=["equipboard.com", "guitarworld.com", "musicradar.com", "premierguitar.com"],
            ),
            ResearchQuery(
                label="producer or studio evidence",
                query=f'"{artist}" "{song.album}" producer studio interview guitar amp pedals',
                rationale="Producer/engineer sources can identify recording-chain details.",
                preferred_domains=["guitarworld.com", "musicradar.com"],
            ),
        ])
    return ToneResearchPlan(song=song, queries=queries)


def _norm(value: str | None) -> str:
    return (value or "").strip().casefold()


def synthesize_tone_hypothesis(song: SongIdentity, evidence: list[ToneEvidence]) -> ToneRigHypothesis:
    gear_scores: dict[tuple[str, str, str, ArrangementRole | None], float] = defaultdict(float)
    gear_urls: dict[tuple[str, str, str, ArrangementRole | None], set[str]] = defaultdict(set)
    effect_scores: dict[tuple[EffectFamily, ArrangementRole | None], float] = defaultdict(float)
    effect_urls: dict[tuple[EffectFamily, ArrangementRole | None], set[str]] = defaultdict(set)
    tone_scores: dict[str, float] = defaultdict(float)

    for item in evidence:
        score = item.authority_score
        for claim in item.gear:
            arrangement = claim.arrangement or item.arrangement
            key = (claim.category, _norm(claim.manufacturer), _norm(claim.model), arrangement)
            gear_scores[key] += score
            gear_urls[key].add(item.url)
        for claim in item.effects:
            arrangement = claim.arrangement or item.arrangement
            key = (claim.family, arrangement)
            effect_scores[key] += score
            effect_urls[key].add(item.url)
        if item.tone_family:
            tone_scores[item.tone_family] += score

    gear = [
        GearCandidate(
            category=category,
            manufacturer=manufacturer or None,
            model=model,
            arrangement=arrangement,
            support_score=round(score, 4),
            evidence_urls=sorted(gear_urls[key]),
        )
        for key, score in gear_scores.items()
        for category, manufacturer, model, arrangement in [key]
    ]
    gear.sort(key=lambda item: (-item.support_score, item.category, item.model))

    effects = [
        EffectCandidate(
            family=family,
            arrangement=arrangement,
            support_score=round(score, 4),
            evidence_urls=sorted(effect_urls[(family, arrangement)]),
        )
        for (family, arrangement), score in effect_scores.items()
    ]
    effects.sort(key=lambda item: (-item.support_score, item.family))

    total_tone = sum(tone_scores.values())
    tone_families = {
        family: round(score / total_tone, 4)
        for family, score in sorted(tone_scores.items(), key=lambda item: -item[1])
    } if total_tone else {}

    warnings: list[str] = []
    grouped: dict[tuple[str, ArrangementRole | None], list[GearCandidate]] = defaultdict(list)
    for candidate in gear:
        grouped[(candidate.category, candidate.arrangement)].append(candidate)
    for (category, arrangement), candidates in grouped.items():
        if len(candidates) > 1 and candidates[1].support_score >= candidates[0].support_score * 0.8:
            label = f"{arrangement + ' ' if arrangement else ''}{category}"
            warnings.append(f"Competing {label} candidates require audio/human review: {candidates[0].model} vs {candidates[1].model}.")
    if not evidence:
        warnings.append("No tone evidence has been collected yet.")

    return ToneRigHypothesis(
        song=song,
        gear=gear,
        effects=effects,
        tone_families=tone_families,
        evidence_count=len(evidence),
        warnings=warnings,
    )
