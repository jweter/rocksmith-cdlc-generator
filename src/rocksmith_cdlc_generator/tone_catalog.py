from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .rocksmith_tone_mapping import ComponentFamily, RocksmithTonePlan

DeviceType = Literal["Amp", "Cabinet", "Pedal", "Rack"]
ToneSlotName = Literal[
    "Amp", "Cabinet",
    "PrePedal1", "PrePedal2", "PrePedal3", "PrePedal4",
    "PostPedal1", "PostPedal2", "PostPedal3", "PostPedal4",
    "Rack1", "Rack2", "Rack3", "Rack4",
]


class ToneKnobDefinition(BaseModel):
    name: str | None = None
    key: str
    default_value: float = 0.0
    minimum_value: float | None = None
    maximum_value: float | None = None


class ToneDevice(BaseModel):
    name: str
    type: str
    category: str | None = None
    key: str
    knobs: list[ToneKnobDefinition] = Field(default_factory=list)
    bass: bool = False
    skin: str | None = None
    skin_index: float | None = None

    @property
    def normalized_type(self) -> DeviceType:
        value = self.type.casefold()
        if value in {"amp", "amps"}:
            return "Amp"
        if value in {"cabinet", "cabinets"}:
            return "Cabinet"
        if value in {"rack", "racks"}:
            return "Rack"
        return "Pedal"

    def pedal2014_payload(self) -> dict:
        return {
            "Type": self.type,
            "KnobValues": {knob.key: knob.default_value for knob in self.knobs},
            "Key": self.key,
            "Category": self.category,
            "Skin": self.skin,
            "SkinIndex": self.skin_index,
        }


class ToneCatalog(BaseModel):
    schema_version: int = 1
    source_sha256: str
    source_format: str = "rocksmith-toolkit-pedals2014"
    devices: list[ToneDevice]

    @model_validator(mode="after")
    def unique_keys(self) -> "ToneCatalog":
        keys = [item.key for item in self.devices]
        if len(keys) != len(set(keys)):
            raise ValueError("tone catalog contains duplicate Rocksmith device keys")
        return self


class BoundToneComponent(BaseModel):
    family: ComponentFamily
    device_key: str | None = None
    device_name: str | None = None
    device_type: str | None = None
    slot: ToneSlotName | None = None
    knob_values: dict[str, float] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    review_required: bool = True
    reason: str


class BoundRocksmithTone(BaseModel):
    arrangement: str
    label: str
    components: list[BoundToneComponent]
    safe_for_injection: bool = False
    warnings: list[str] = Field(default_factory=list)


class BoundRocksmithTonePlan(BaseModel):
    schema_version: int = 1
    artist: str
    title: str
    catalog_sha256: str
    tones: list[BoundRocksmithTone]
    safe_for_automatic_injection: bool = False
    warnings: list[str] = Field(default_factory=list)


def _coerce_knob(raw: dict) -> ToneKnobDefinition:
    return ToneKnobDefinition(
        name=raw.get("Name"),
        key=str(raw.get("Key") or raw.get("key") or ""),
        default_value=float(raw.get("DefaultValue", raw.get("defaultValue", 0.0))),
        minimum_value=raw.get("MinimumValue", raw.get("minimumValue")),
        maximum_value=raw.get("MaximumValue", raw.get("maximumValue")),
    )


def load_toolkit_pedals2014(path: Path) -> ToneCatalog:
    """Load a user-derived Rocksmith Toolkit pedals2014.json catalog.

    The file is expected to have been generated from the user's own Rocksmith 2014
    gear manifests, following the upstream Toolkit pedalgen format. The generator
    intentionally does not redistribute Ubisoft gear manifests or a copied catalog.
    """
    raw_bytes = path.read_bytes()
    payload = json.loads(raw_bytes.decode("utf-8-sig"))
    if not isinstance(payload, list):
        raise ValueError("pedals2014 catalog must be a JSON array")

    devices: list[ToneDevice] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("each pedals2014 entry must be an object")
        name = item.get("Name")
        key = item.get("Key")
        type_name = item.get("Type")
        if not name or not key or not type_name:
            raise ValueError("pedals2014 entries require Name, Key, and Type")
        devices.append(
            ToneDevice(
                name=str(name),
                type=str(type_name),
                category=item.get("Category"),
                key=str(key),
                knobs=[_coerce_knob(knob) for knob in (item.get("Knobs") or [])],
                bass=bool(item.get("Bass", False)),
                skin=item.get("Skin"),
                skin_index=item.get("SkinIndex"),
            )
        )

    return ToneCatalog(
        source_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        devices=devices,
    )


def write_catalog(catalog: ToneCatalog, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(catalog.model_dump_json(indent=2), encoding="utf-8")
    return destination


_FAMILY_TERMS: dict[ComponentFamily, tuple[str, ...]] = {
    "amp_clean": ("clean", "vintage", "combo", "jazz"),
    "amp_crunch": ("crunch", "brit", "classic", "plexi", "rock"),
    "amp_high_gain": ("high gain", "metal", "modern", "rect", "lead"),
    "amp_fuzz": ("fuzz", "dirty", "gain"),
    "compressor": ("compress",),
    "boost": ("boost",),
    "overdrive": ("overdrive", "drive", "screamer"),
    "distortion": ("distortion", "dist"),
    "fuzz": ("fuzz",),
    "wah_filter": ("wah", "filter"),
    "chorus": ("chorus",),
    "flanger": ("flanger", "flange"),
    "phaser": ("phaser", "phase"),
    "tremolo": ("tremolo",),
    "vibrato": ("vibrato",),
    "rotary": ("rotary", "leslie"),
    "delay": ("delay", "echo"),
    "reverb": ("reverb", "verb"),
    "octave_pitch": ("octave", "pitch", "whammy"),
    "noise_gate": ("noise gate", "gate"),
    "eq": ("equalizer", "eq"),
}


def _device_text(device: ToneDevice) -> str:
    return " ".join(filter(None, [device.name, device.category, device.type])).casefold()


def _candidate_devices(catalog: ToneCatalog, family: ComponentFamily, *, bass: bool) -> list[tuple[int, ToneDevice]]:
    amp_family = family.startswith("amp_")
    scored: list[tuple[int, ToneDevice]] = []
    for device in catalog.devices:
        kind = device.normalized_type
        if amp_family and kind != "Amp":
            continue
        if not amp_family and kind not in {"Pedal", "Rack"}:
            continue
        text = _device_text(device)
        score = sum(3 for term in _FAMILY_TERMS[family] if term in text)
        if device.bass == bass:
            score += 2
        elif device.bass and not bass:
            score -= 2
        if score > 0:
            scored.append((score, device))
    return sorted(scored, key=lambda item: (-item[0], item[1].name.casefold(), item[1].key))


def _slot_for(device: ToneDevice, used: set[str]) -> ToneSlotName | None:
    kind = device.normalized_type
    if kind == "Amp":
        return "Amp" if "Amp" not in used else None
    if kind == "Cabinet":
        return "Cabinet" if "Cabinet" not in used else None
    prefix = "Rack" if kind == "Rack" else "PrePedal"
    for index in range(1, 5):
        slot = f"{prefix}{index}"
        if slot not in used:
            return slot  # type: ignore[return-value]
    return None


def bind_tone_plan_to_catalog(plan: RocksmithTonePlan, catalog: ToneCatalog) -> BoundRocksmithTonePlan:
    """Bind abstract tone families to real Rocksmith device keys conservatively.

    Matching is deterministic but intentionally review-gated. Names/categories from
    the locally derived catalog are used only to create candidates; no device is
    treated as historically exact merely because its label resembles researched gear.
    """
    tones: list[BoundRocksmithTone] = []
    global_warnings: list[str] = []
    for tone in plan.tones:
        bass = tone.arrangement == "bass"
        used: set[str] = set()
        bound: list[BoundToneComponent] = []
        warnings = list(tone.warnings)
        for suggestion in tone.components:
            candidates = _candidate_devices(catalog, suggestion.family, bass=bass)
            if not candidates:
                bound.append(BoundToneComponent(
                    family=suggestion.family,
                    confidence=0.0,
                    review_required=True,
                    reason="No compatible Rocksmith catalog device matched this component family.",
                ))
                warnings.append(f"No Rocksmith device matched {suggestion.family}.")
                continue
            best_score, device = candidates[0]
            second_score = candidates[1][0] if len(candidates) > 1 else None
            ambiguous = second_score is not None and second_score >= best_score
            slot = _slot_for(device, used)
            if slot is None:
                warnings.append(f"No free Rocksmith slot for {device.name} ({suggestion.family}).")
                bound.append(BoundToneComponent(
                    family=suggestion.family,
                    device_key=device.key,
                    device_name=device.name,
                    device_type=device.type,
                    confidence=min(0.5, suggestion.confidence),
                    review_required=True,
                    reason="Catalog match found but no compatible tone slot remained.",
                ))
                continue
            used.add(slot)
            confidence = min(suggestion.confidence, 0.82 if not ambiguous else 0.58)
            bound.append(BoundToneComponent(
                family=suggestion.family,
                device_key=device.key,
                device_name=device.name,
                device_type=device.type,
                slot=slot,
                knob_values={knob.key: knob.default_value for knob in device.knobs},
                confidence=round(confidence, 4),
                review_required=True,
                reason=(
                    "Deterministic local-catalog family match; exact tone and knob values still require review."
                    if not ambiguous else
                    "Multiple equally ranked local-catalog devices matched this family; selected deterministically for review."
                ),
            ))
            if ambiguous:
                warnings.append(f"Ambiguous Rocksmith catalog match for {suggestion.family}; review {device.name}.")

        tones.append(BoundRocksmithTone(
            arrangement=tone.arrangement,
            label=tone.label,
            components=bound,
            safe_for_injection=False,
            warnings=warnings,
        ))

    global_warnings.extend(plan.warnings)
    global_warnings.append(
        "Catalog binding uses a locally derived Rocksmith device catalog and remains human-review gated; default knob values are not claims about the recording rig."
    )
    return BoundRocksmithTonePlan(
        artist=plan.artist,
        title=plan.title,
        catalog_sha256=catalog.source_sha256,
        tones=tones,
        safe_for_automatic_injection=False,
        warnings=global_warnings,
    )
