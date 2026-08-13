from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SourceKind = Literal[
    "guitar_pro",
    "midi",
    "musicxml",
    "hand_corrected",
    "existing_cdlc",
    "other",
]

RedistributionStatus = Literal[
    "redistributable",
    "local_only",
    "unknown",
]


class BenchmarkSourceProvenance(BaseModel):
    """Metadata-only provenance for one benchmark reference source.

    The source bytes and local filesystem path are intentionally outside this
    model so copyrighted/non-redistributable material cannot be promoted into
    committed benchmark metadata by accident.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    benchmark_id: str = Field(pattern=r"^BMARK-\d{3}$")
    source_label: str = Field(min_length=1)
    source_kind: SourceKind
    acquisition_license_note: str = Field(min_length=1)
    redistribution_status: RedistributionStatus
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    accepted_by_human: bool = False
    accepted_by: str | None = None
    acceptance_date: date | None = None
    known_limitations: tuple[str, ...] = ()

    @field_validator("source_label", "acquisition_license_note")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("provenance text must contain a non-whitespace character")
        return stripped

    @model_validator(mode="after")
    def validate_acceptance_gate(self) -> "BenchmarkSourceProvenance":
        if self.accepted_by_human:
            if not self.accepted_by or not self.accepted_by.strip():
                raise ValueError("accepted_by is required when accepted_by_human is true")
            if self.acceptance_date is None:
                raise ValueError("acceptance_date is required when accepted_by_human is true")
        elif self.accepted_by is not None or self.acceptance_date is not None:
            raise ValueError(
                "accepted_by and acceptance_date must remain unset until human acceptance"
            )
        return self
