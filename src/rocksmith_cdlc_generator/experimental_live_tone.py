from __future__ import annotations

from typing import Literal

from .audition_dsp import AuditionChain, AuditionEffectSpec, validate_audition_chain

InputLevelStatus = Literal["healthy", "hot", "clipping"]


EXPERIMENTAL_LIVE_TONE_PRESETS: dict[str, AuditionChain] = {
    "clean": AuditionChain(
        name="Clean boost",
        variant="manual",
        sample_rate_hz=48_000,
        effects=[
            AuditionEffectSpec(
                effect_type="gain",
                label="Clean level",
                parameters={"linear": 1.15},
                mapping_confidence="approximate",
            )
        ],
    ),
    "crunch": AuditionChain(
        name="Generic crunch",
        variant="manual",
        sample_rate_hz=48_000,
        effects=[
            AuditionEffectSpec(
                effect_type="gain",
                label="Pre gain",
                parameters={"linear": 1.8},
                mapping_confidence="approximate",
            ),
            AuditionEffectSpec(
                effect_type="soft_clip",
                label="Soft clip",
                parameters={"drive": 2.4},
                mapping_confidence="approximate",
            ),
            AuditionEffectSpec(
                effect_type="gain",
                label="Output trim",
                parameters={"linear": 0.65},
                mapping_confidence="approximate",
            ),
        ],
    ),
    "drive": AuditionChain(
        name="Generic drive",
        variant="manual",
        sample_rate_hz=48_000,
        effects=[
            AuditionEffectSpec(
                effect_type="gain",
                label="Pre gain",
                parameters={"linear": 2.4},
                mapping_confidence="approximate",
            ),
            AuditionEffectSpec(
                effect_type="soft_clip",
                label="Soft clip",
                parameters={"drive": 4.0},
                mapping_confidence="approximate",
            ),
            AuditionEffectSpec(
                effect_type="gain",
                label="Output trim",
                parameters={"linear": 0.52},
                mapping_confidence="approximate",
            ),
        ],
    ),
}


def build_experimental_live_tone_preset(name: str) -> AuditionChain:
    try:
        preset = EXPERIMENTAL_LIVE_TONE_PRESETS[name]
    except KeyError as exc:
        raise ValueError(f"unknown experimental live tone preset: {name}") from exc
    chain = preset.model_copy(deep=True)
    validate_audition_chain(chain)
    return chain


def classify_input_level(peak_input_level: float) -> InputLevelStatus:
    """Classify measured full-scale input level for operator feedback.

    1.0 is digital full scale for the float32 stream. Values at or above 0.99 are
    treated as clipping-risk evidence; 0.90-0.99 is deliberately called hot so
    the operator can add headroom before judging tone quality.
    """

    magnitude = abs(float(peak_input_level))
    if magnitude >= 0.99:
        return "clipping"
    if magnitude >= 0.90:
        return "hot"
    return "healthy"
