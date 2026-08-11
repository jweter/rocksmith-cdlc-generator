from __future__ import annotations

import math
from typing import Literal, Protocol

from pydantic import BaseModel, Field, model_validator

MappingConfidence = Literal["exact", "approximate", "unsupported"]
AuditionVariant = Literal["original", "proposed", "manual"]


class AuditionEffectSpec(BaseModel):
    effect_type: str = Field(min_length=1)
    label: str = Field(min_length=1)
    parameters: dict[str, float] = Field(default_factory=dict)
    source_device_key: str | None = None
    mapping_confidence: MappingConfidence = "approximate"
    unsupported_parameters: list[str] = Field(default_factory=list)
    bypassed: bool = False


class AuditionChain(BaseModel):
    schema_version: int = 1
    name: str = Field(min_length=1)
    variant: AuditionVariant
    sample_rate_hz: int = Field(gt=0)
    effects: list[AuditionEffectSpec] = Field(default_factory=list)
    bypassed: bool = False

    @model_validator(mode="after")
    def validate_unique_labels(self) -> "AuditionChain":
        labels = [item.label.casefold() for item in self.effects]
        if len(labels) != len(set(labels)):
            raise ValueError("audition chain effect labels must be unique")
        return self


class AuditionProcessor(Protocol):
    def process(self, samples: list[float], chain: AuditionChain) -> list[float]: ...


def validate_audition_chain(chain: AuditionChain) -> None:
    """Fail closed on unsupported/unsafe approximation metadata."""
    for effect in chain.effects:
        if effect.mapping_confidence == "unsupported" and not effect.bypassed:
            raise ValueError(
                f"unsupported audition effect must remain bypassed: {effect.label}"
            )
        for name, value in effect.parameters.items():
            if not math.isfinite(value):
                raise ValueError(f"audition parameter must be finite: {effect.label}/{name}")


def select_ab_chain(
    *,
    original: AuditionChain,
    proposed: AuditionChain,
    selected: Literal["A", "B"],
) -> AuditionChain:
    """Return the selected chain without mutating either candidate."""
    if original.sample_rate_hz != proposed.sample_rate_hz:
        raise ValueError("A/B chains must use the same sample rate")
    return (original if selected == "A" else proposed).model_copy(deep=True)


class ReferenceAuditionProcessor:
    """Tiny deterministic CI/reference processor, not a production guitar modeler.

    Supported effect types are intentionally generic and limited. Production realtime
    DSP backends can implement the same AuditionProcessor contract later.
    """

    def process(self, samples: list[float], chain: AuditionChain) -> list[float]:
        validate_audition_chain(chain)
        result = [float(item) for item in samples]
        if chain.bypassed:
            return result

        for effect in chain.effects:
            if effect.bypassed:
                continue
            if effect.effect_type == "gain":
                gain = effect.parameters.get("linear", 1.0)
                result = [sample * gain for sample in result]
            elif effect.effect_type == "soft_clip":
                drive = effect.parameters.get("drive", 1.0)
                result = [math.tanh(sample * drive) for sample in result]
            elif effect.effect_type == "lowpass_one_pole":
                alpha = effect.parameters.get("alpha", 0.5)
                if not 0.0 <= alpha <= 1.0:
                    raise ValueError("lowpass_one_pole alpha must be between 0 and 1")
                if result:
                    previous = result[0]
                    filtered = [previous]
                    for sample in result[1:]:
                        previous = alpha * sample + (1.0 - alpha) * previous
                        filtered.append(previous)
                    result = filtered
            else:
                raise ValueError(f"reference processor does not support effect type: {effect.effect_type}")
        return result
