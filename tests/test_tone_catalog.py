from __future__ import annotations

import json
from pathlib import Path

from rocksmith_cdlc_generator.rocksmith_tone_mapping import (
    RocksmithTonePlan,
    RocksmithToneSuggestion,
    ToneComponentSuggestion,
)
from rocksmith_cdlc_generator.tone_catalog import (
    ToneCatalog,
    ToneDevice,
    ToneKnobDefinition,
    bind_tone_plan_to_catalog,
    load_toolkit_pedals2014,
)


def test_load_toolkit_pedals2014(tmp_path: Path) -> None:
    source = tmp_path / "pedals2014.json"
    source.write_text(json.dumps([
        {
            "Name": "Vintage Clean Combo",
            "Type": "Amp",
            "Category": "Amps",
            "Key": "amp_clean_key",
            "Knobs": [{"Name": "Gain", "Key": "Gain", "DefaultValue": 0.35}],
            "Bass": False,
            "Skin": "clean_skin",
            "SkinIndex": 0.0,
        }
    ]), encoding="utf-8")

    catalog = load_toolkit_pedals2014(source)
    assert len(catalog.devices) == 1
    device = catalog.devices[0]
    assert device.normalized_type == "Amp"
    assert device.key == "amp_clean_key"
    assert device.pedal2014_payload()["KnobValues"] == {"Gain": 0.35}
    assert len(catalog.source_sha256) == 64


def test_duplicate_catalog_keys_rejected() -> None:
    duplicate = ToneDevice(name="A", type="Amp", key="same")
    try:
        ToneCatalog(source_sha256="0" * 64, devices=[duplicate, duplicate])
    except ValueError as exc:
        assert "duplicate" in str(exc).lower()
    else:
        raise AssertionError("duplicate Rocksmith keys must fail")


def _plan() -> RocksmithTonePlan:
    return RocksmithTonePlan(
        artist="Artist",
        title="Song",
        source_evidence_count=2,
        tones=[
            RocksmithToneSuggestion(
                slot="base",
                arrangement="lead",
                label="Lead Base",
                tone_family="high_gain",
                confidence=0.9,
                components=[
                    ToneComponentSuggestion(
                        family="amp_high_gain",
                        reason="research",
                        confidence=0.9,
                    ),
                    ToneComponentSuggestion(
                        family="delay",
                        reason="research",
                        confidence=0.8,
                    ),
                ],
                review_required=True,
            )
        ],
        safe_for_automatic_injection=False,
    )


def test_bind_tone_plan_uses_real_catalog_keys_and_default_knobs() -> None:
    catalog = ToneCatalog(
        source_sha256="a" * 64,
        devices=[
            ToneDevice(
                name="Modern High Gain Lead",
                type="Amp",
                category="Amps",
                key="amp_hg",
                knobs=[ToneKnobDefinition(key="Gain", default_value=0.7)],
            ),
            ToneDevice(
                name="Studio Delay",
                type="Rack",
                category="Delay",
                key="rack_delay",
                knobs=[ToneKnobDefinition(key="Mix", default_value=0.25)],
            ),
        ],
    )

    bound = bind_tone_plan_to_catalog(_plan(), catalog)
    assert bound.safe_for_automatic_injection is False
    tone = bound.tones[0]
    assert tone.components[0].device_key == "amp_hg"
    assert tone.components[0].slot == "Amp"
    assert tone.components[0].knob_values == {"Gain": 0.7}
    assert tone.components[1].device_key == "rack_delay"
    assert tone.components[1].slot == "Rack1"
    assert all(component.review_required for component in tone.components)


def test_missing_family_remains_unresolved() -> None:
    catalog = ToneCatalog(
        source_sha256="b" * 64,
        devices=[ToneDevice(name="Clean Combo", type="Amp", category="Amps", key="clean")],
    )
    plan = RocksmithTonePlan(
        artist="Artist",
        title="Song",
        source_evidence_count=1,
        tones=[
            RocksmithToneSuggestion(
                slot="base",
                arrangement="lead",
                label="Lead Base",
                tone_family="clean",
                confidence=0.8,
                components=[ToneComponentSuggestion(family="phaser", reason="research", confidence=0.8)],
                review_required=True,
            )
        ],
    )
    bound = bind_tone_plan_to_catalog(plan, catalog)
    component = bound.tones[0].components[0]
    assert component.device_key is None
    assert component.confidence == 0.0
    assert any("No Rocksmith device matched phaser" in warning for warning in bound.tones[0].warnings)


def test_bass_catalog_preference() -> None:
    plan = RocksmithTonePlan(
        artist="Artist",
        title="Song",
        source_evidence_count=1,
        tones=[
            RocksmithToneSuggestion(
                slot="base",
                arrangement="bass",
                label="Bass Base",
                tone_family="clean",
                confidence=0.8,
                components=[ToneComponentSuggestion(family="compressor", reason="research", confidence=0.8)],
                review_required=True,
            )
        ],
    )
    catalog = ToneCatalog(
        source_sha256="c" * 64,
        devices=[
            ToneDevice(name="Compressor", type="Pedal", category="Compression", key="gtr_comp", bass=False),
            ToneDevice(name="Bass Compressor", type="Pedal", category="Compression", key="bass_comp", bass=True),
        ],
    )
    bound = bind_tone_plan_to_catalog(plan, catalog)
    assert bound.tones[0].components[0].device_key == "bass_comp"
