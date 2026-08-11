from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .tone_reference_library import (
    ArrangementRole,
    LocalToneReference,
    ReferenceSourceType,
    ReferenceToneComponent,
)

_GEAR_SLOTS = (
    "Amp", "Cabinet",
    "PrePedal1", "PrePedal2", "PrePedal3", "PrePedal4",
    "PostPedal1", "PostPedal2", "PostPedal3", "PostPedal4",
    "Rack1", "Rack2", "Rack3", "Rack4",
)


def _arrangement_role(attributes: dict[str, Any]) -> ArrangementRole:
    props = attributes.get("ArrangementProperties") or {}
    if props.get("PathBass") == 1:
        return "bass"
    if props.get("PathLead") == 1:
        return "lead"
    if props.get("PathRhythm") == 1:
        return "rhythm"

    name = str(attributes.get("ArrangementName") or "").casefold()
    if "bass" in name:
        return "bass"
    if "lead" in name:
        return "lead"
    if "rhythm" in name:
        return "rhythm"
    return "other"


def _components(gear: Any) -> list[ReferenceToneComponent]:
    if not isinstance(gear, dict):
        return []
    result: list[ReferenceToneComponent] = []
    for slot in _GEAR_SLOTS:
        device = gear.get(slot)
        if not isinstance(device, dict):
            continue
        key = device.get("Key")
        if not isinstance(key, str) or not key.strip():
            continue
        raw_knobs = device.get("KnobValues") or {}
        knobs: dict[str, float] = {}
        if isinstance(raw_knobs, dict):
            for knob, value in raw_knobs.items():
                if isinstance(knob, str) and isinstance(value, (int, float)) and not isinstance(value, bool):
                    knobs[knob] = float(value)
        result.append(ReferenceToneComponent(slot=slot, device_key=key, knob_values=knobs))
    return result


def _iter_attributes(payload: Any):
    if not isinstance(payload, dict):
        return
    entries = payload.get("Entries")
    if not isinstance(entries, dict):
        return
    for outer in entries.values():
        if not isinstance(outer, dict):
            continue
        for attributes in outer.values():
            if isinstance(attributes, dict):
                yield attributes


def parse_tone_manifest_payload(
    payload: Any,
    *,
    source_psarc_sha256: str,
    source_path: str,
    source_type: ReferenceSourceType = "unknown",
) -> list[LocalToneReference]:
    """Parse supported Rocksmith 2014 song-manifest tone data conservatively.

    The supported schema is the Manifest2014<Attributes2014> shape used by the
    pinned Rocksmith Custom Song Toolkit model. Missing or malformed tone fields
    are skipped rather than guessed. Tone-change timestamps are intentionally not
    synthesized here; those require arrangement/SNG evidence in a later adapter.
    """
    records: list[LocalToneReference] = []
    for attributes in _iter_attributes(payload) or ():
        arrangement_name = str(attributes.get("ArrangementName") or "")
        if arrangement_name.casefold() in {"vocals", "jvocals"}:
            continue
        tones = attributes.get("Tones")
        if not isinstance(tones, list):
            continue

        artist = attributes.get("ArtistName")
        title = attributes.get("SongName")
        if not isinstance(artist, str) or not artist.strip():
            continue
        if not isinstance(title, str) or not title.strip():
            continue
        arrangement = _arrangement_role(attributes)

        for tone in tones:
            if not isinstance(tone, dict):
                continue
            key = tone.get("Key")
            name = tone.get("Name")
            if not isinstance(key, str) or not key.strip():
                continue
            components = _components(tone.get("GearList"))
            if not components:
                continue
            descriptors = [
                value for value in (tone.get("ToneDescriptors") or [])
                if isinstance(value, str) and value.strip()
            ] if isinstance(tone.get("ToneDescriptors") or [], list) else []
            records.append(LocalToneReference(
                source_psarc_sha256=source_psarc_sha256,
                source_path=source_path,
                source_type=source_type,
                artist=artist,
                title=title,
                arrangement=arrangement,
                arrangement_name=arrangement_name or None,
                tone_key=key,
                tone_name=name if isinstance(name, str) and name.strip() else None,
                tone_descriptors=descriptors,
                components=components,
                tone_changes=[],
            ))
    return records


def parse_tone_manifest_file(
    path: Path,
    *,
    source_psarc_sha256: str,
    source_path: str,
    source_type: ReferenceSourceType = "unknown",
) -> list[LocalToneReference]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return parse_tone_manifest_payload(
        payload,
        source_psarc_sha256=source_psarc_sha256,
        source_path=source_path,
        source_type=source_type,
    )
