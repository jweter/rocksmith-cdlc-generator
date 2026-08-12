from __future__ import annotations

from typing import Literal

from .audition_dsp import AuditionChain, AuditionEffectSpec, validate_audition_chain

InputLevelStatus = Literal["healthy", "hot", "clipping_risk", "full_scale"]


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
    """Classify measured float32 input level for operator feedback.

    A measured magnitude of 1.0 is digital full scale. Values from 0.99 up to,
    but not including, 1.0 are near full scale and therefore a clipping risk,
    not proof that clipping occurred. Values from 0.90 to 0.99 are called hot.
    """

    magnitude = abs(float(peak_input_level))
    if magnitude >= 1.0:
        return "full_scale"
    if magnitude >= 0.99:
        return "clipping_risk"
    if magnitude >= 0.90:
        return "hot"
    return "healthy"
