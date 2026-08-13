from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BenchmarkPromotionRecord(BaseModel):
    """Metadata-only checklist for promoting a candidate into the trusted corpus."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    benchmark_id: str = Field(pattern=r"^BMARK-[0-9]{3}$")
    library_absence_verified: bool = False
    lawful_local_audio_available: bool = False
    reference_source_available: bool = False
    reference_accepted_by_human: bool = False
    excerpt_start_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    excerpt_end_seconds: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    provenance_recorded: bool = False

    @model_validator(mode="after")
    def validate_excerpt(self) -> "BenchmarkPromotionRecord":
        start = self.excerpt_start_seconds
        end = self.excerpt_end_seconds
        if (start is None) != (end is None):
            raise ValueError("excerpt start and end must be provided together")
        if start is not None and end is not None:
            duration = end - start
            if duration < 30 or duration > 90:
                raise ValueError("trusted benchmark excerpt must be 30 to 90 seconds")
        return self

    @property
    def ready_for_trusted_benchmark(self) -> bool:
        return all(
            (
                self.library_absence_verified,
                self.lawful_local_audio_available,
                self.reference_source_available,
                self.reference_accepted_by_human,
                self.excerpt_start_seconds is not None,
                self.excerpt_end_seconds is not None,
                self.provenance_recorded,
            )
        )

    @property
    def blocking_reasons(self) -> tuple[str, ...]:
        reasons: list[str] = []
        if not self.library_absence_verified:
            reasons.append("library_absence_not_verified")
        if not self.lawful_local_audio_available:
            reasons.append("lawful_local_audio_not_available")
        if not self.reference_source_available:
            reasons.append("reference_source_not_available")
        if not self.reference_accepted_by_human:
            reasons.append("reference_not_accepted_by_human")
        if self.excerpt_start_seconds is None or self.excerpt_end_seconds is None:
            reasons.append("excerpt_not_selected")
        if not self.provenance_recorded:
            reasons.append("provenance_not_recorded")
        return tuple(reasons)
