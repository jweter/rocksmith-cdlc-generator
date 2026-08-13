from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class CandidateBankValidationError(ValueError):
    pass


class Tier(StrEnum):
    TIER_1_MVP = "tier_1_mvp"
    TIER_2_GENERALIZATION = "tier_2_generalization"
    TIER_3_ADVANCED = "tier_3_advanced"
    TIER_4_STRESS = "tier_4_stress"
    RESERVE = "reserve"


class StructuredReferenceStatus(StrEnum):
    VERIFIED_STRONG = "verified_strong"
    VERIFIED_GOOD = "verified_good"
    PROVISIONAL = "provisional"


class DlcLibraryStatus(StrEnum):
    MANUAL_SEARCH_NO_EXACT_MATCH = "manual_search_no_exact_match"
    REQUIRES_FULL_CFSM_CHECK = "requires_full_cfsm_check"


class StructuredReference(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: StructuredReferenceStatus
    kind: str = Field(min_length=1)
    notes: str | None = None


class DlcLibrary(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: DlcLibraryStatus
    notes: str | None = None


class Candidate(BaseModel):
    model_config = ConfigDict(extra="allow")
    rank: int = Field(ge=1)
    benchmark_id: str = Field(pattern=r"^BMARK-[0-9]{3}$")
    artist: str = Field(min_length=1)
    title: str = Field(min_length=1)
    duration_seconds: float | None = Field(default=None, gt=0)
    tier: Tier
    role: str = Field(min_length=1)
    structured_reference: StructuredReference
    dlc_library: DlcLibrary
    rationale: str = Field(min_length=1)


class CandidateBank(BaseModel):
    model_config = ConfigDict(extra="allow")
    schema_version: int
    purpose: str = Field(min_length=1)
    promotion_policy: dict[str, Any]
    candidates: list[Candidate] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_bank(self) -> "CandidateBank":
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")
        ranks = [item.rank for item in self.candidates]
        ids = [item.benchmark_id for item in self.candidates]
        if len(ranks) != len(set(ranks)):
            raise ValueError("candidate ranks must be unique")
        if len(ids) != len(set(ids)):
            raise ValueError("benchmark_id values must be unique")
        if ranks != list(range(1, len(ranks) + 1)):
            raise ValueError("candidate ranks must be contiguous starting at 1")
        return self


def validate_candidate_bank(path: Path) -> CandidateBank:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"candidate bank not found: {path}")
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CandidateBankValidationError(f"candidate bank is not valid YAML: {exc}") from exc
    if not isinstance(payload, dict):
        raise CandidateBankValidationError("candidate bank YAML root must be an object")
    try:
        return CandidateBank.model_validate(payload)
    except ValueError as exc:
        raise CandidateBankValidationError(str(exc)) from exc
