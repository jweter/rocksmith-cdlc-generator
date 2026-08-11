import math

import pytest

from rocksmith_cdlc_generator.audition_dsp import (
    AuditionChain,
    AuditionEffectSpec,
    ReferenceAuditionProcessor,
    select_ab_chain,
    validate_audition_chain,
)


def _chain(*, variant: str = "proposed") -> AuditionChain:
    return AuditionChain(
        name="Synthetic Lead",
        variant=variant,
        sample_rate_hz=48000,
        effects=[
            AuditionEffectSpec(
                effect_type="gain",
                label="input gain",
                parameters={"linear": 2.0},
                source_device_key="synthetic_amp",
                mapping_confidence="approximate",
            ),
            AuditionEffectSpec(
                effect_type="soft_clip",
                label="drive",
                parameters={"drive": 1.5},
                source_device_key="synthetic_drive",
                mapping_confidence="approximate",
            ),
        ],
    )


def test_reference_processor_is_deterministic_and_non_mutating() -> None:
    chain = _chain()
    before = chain.model_dump()
    samples = [-0.5, 0.0, 0.5]

    processor = ReferenceAuditionProcessor()
    first = processor.process(samples, chain)
    second = processor.process(samples, chain)

    assert first == second
    assert chain.model_dump() == before
    assert samples == [-0.5, 0.0, 0.5]
    assert first[1] == 0.0
    assert first[2] > 0.5


def test_chain_bypass_returns_dry_copy() -> None:
    chain = _chain().model_copy(update={"bypassed": True})
    samples = [0.1, -0.2, 0.3]

    result = ReferenceAuditionProcessor().process(samples, chain)

    assert result == samples
    assert result is not samples


def test_unsupported_mapping_must_remain_bypassed() -> None:
    chain = AuditionChain(
        name="Unsupported",
        variant="proposed",
        sample_rate_hz=48000,
        effects=[
            AuditionEffectSpec(
                effect_type="mystery",
                label="unknown device",
                mapping_confidence="unsupported",
                bypassed=False,
            )
        ],
    )

    with pytest.raises(ValueError, match="unsupported audition effect must remain bypassed"):
        validate_audition_chain(chain)


def test_non_finite_parameters_fail_closed() -> None:
    chain = AuditionChain(
        name="Bad",
        variant="manual",
        sample_rate_hz=48000,
        effects=[
            AuditionEffectSpec(
                effect_type="gain",
                label="gain",
                parameters={"linear": math.inf},
            )
        ],
    )

    with pytest.raises(ValueError, match="must be finite"):
        validate_audition_chain(chain)


def test_ab_selection_requires_matching_sample_rates_and_returns_copy() -> None:
    original = _chain(variant="original")
    proposed = _chain(variant="proposed")

    selected = select_ab_chain(original=original, proposed=proposed, selected="B")

    assert selected.variant == "proposed"
    assert selected is not proposed
    selected.effects[0].parameters["linear"] = 9.0
    assert proposed.effects[0].parameters["linear"] == 2.0

    mismatched = proposed.model_copy(update={"sample_rate_hz": 44100})
    with pytest.raises(ValueError, match="same sample rate"):
        select_ab_chain(original=original, proposed=mismatched, selected="A")


def test_lowpass_parameter_range_is_enforced() -> None:
    chain = AuditionChain(
        name="Lowpass",
        variant="manual",
        sample_rate_hz=48000,
        effects=[
            AuditionEffectSpec(
                effect_type="lowpass_one_pole",
                label="tone filter",
                parameters={"alpha": 1.5},
            )
        ],
    )

    with pytest.raises(ValueError, match="alpha must be between 0 and 1"):
        ReferenceAuditionProcessor().process([0.0, 1.0], chain)
