from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

ReferenceSource = Literal["official_rocksmith", "custom_dlc", "user_created", "unknown"]
ArrangementRole = Literal["lead", "rhythm", "bass"]

_SOURCE_WEIGHT: dict[ReferenceSource, float] = {
    "official_rocksmith": 1.0,
    "custom_dlc": 0.65,
    "user_created": 0.75,
    "unknown": 0.45,
}


class ReferenceToneComponent(BaseModel):
    slot: str
    device_key: str
    device_name: str | None = None
    device_type: str | None = None
    category: str | None = None
    knob_values: dict[str, float] = Field(default_factory=dict)


class ToneChangeReference(BaseModel):
    time_seconds: float = Field(ge=0.0)
    tone_key: str


class LocalToneReference(BaseModel):
    schema_version: int = 1
    source_psarc_sha256: str = Field(min_length=64, max_length=64)
    source_path: str
    source_type: ReferenceSource = "unknown"
    artist: str | None = None
    title: str | None = None
    album: str | None = None
    arrangement: ArrangementRole
    tone_key: str
    tone_name: str | None = None
    tone_descriptors: list[str] = Field(default_factory=list)
    volume: float | None = None
    components: list[ReferenceToneComponent] = Field(default_factory=list)
    tone_changes: list[ToneChangeReference] = Field(default_factory=list)

    @property
    def authority_weight(self) -> float:
        return _SOURCE_WEIGHT[self.source_type]

    @property
    def fingerprint(self) -> str:
        payload = {
            "components": [
                {
                    "slot": item.slot,
                    "device_key": item.device_key,
                    "knob_values": dict(sorted(item.knob_values.items())),
                }
                for item in sorted(self.components, key=lambda item: (item.slot, item.device_key))
            ],
            "descriptors": sorted(self.tone_descriptors),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class ScannedPsarcRecord(BaseModel):
    path: str
    sha256: str = Field(min_length=64, max_length=64)
    size_bytes: int = Field(ge=0)
    modified_ns: int = Field(ge=0)
    source_type: ReferenceSource = "unknown"
    tone_count: int = Field(ge=0)


class ToneReferenceLibrary(BaseModel):
    schema_version: int = 1
    scan_root: str
    psarcs: list[ScannedPsarcRecord] = Field(default_factory=list)
    tones: list[LocalToneReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_psarc_paths(self) -> "ToneReferenceLibrary":
        paths = [item.path.casefold() for item in self.psarcs]
        if len(paths) != len(set(paths)):
            raise ValueError("tone reference library contains duplicate PSARC paths")
        return self

    @property
    def official_tone_count(self) -> int:
        return sum(item.source_type == "official_rocksmith" for item in self.tones)

    def find_similar(
        self,
        *,
        arrangement: ArrangementRole,
        device_keys: set[str] | None = None,
        descriptors: set[str] | None = None,
        limit: int = 10,
    ) -> list[tuple[float, LocalToneReference]]:
        if limit <= 0:
            return []
        wanted_keys = {item.casefold() for item in (device_keys or set())}
        wanted_desc = {item.casefold() for item in (descriptors or set())}
        ranked: list[tuple[float, LocalToneReference]] = []
        for tone in self.tones:
            if tone.arrangement != arrangement:
                continue
            keys = {item.device_key.casefold() for item in tone.components}
            desc = {item.casefold() for item in tone.tone_descriptors}
            key_overlap = len(keys & wanted_keys) / max(1, len(wanted_keys)) if wanted_keys else 0.0
            desc_overlap = len(desc & wanted_desc) / max(1, len(wanted_desc)) if wanted_desc else 0.0
            score = tone.authority_weight * (0.15 + 0.65 * key_overlap + 0.20 * desc_overlap)
            ranked.append((round(score, 4), tone))
        ranked.sort(key=lambda item: (-item[0], item[1].artist or "", item[1].title or "", item[1].tone_key))
        return ranked[:limit]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_psarcs(root: Path) -> list[Path]:
    root = root.resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)
    return sorted((item for item in root.rglob("*.psarc") if item.is_file()), key=lambda item: str(item).casefold())


def changed_psarcs(root: Path, existing: ToneReferenceLibrary | None = None) -> list[Path]:
    prior = {Path(item.path).resolve(): item for item in (existing.psarcs if existing else [])}
    changed: list[Path] = []
    for path in discover_psarcs(root):
        stat = path.stat()
        old = prior.get(path.resolve())
        if old is None or old.size_bytes != stat.st_size or old.modified_ns != stat.st_mtime_ns:
            changed.append(path)
    return changed


def merge_scan_results(
    root: Path,
    extracted: list[tuple[Path, ReferenceSource, list[LocalToneReference]]],
    existing: ToneReferenceLibrary | None = None,
) -> ToneReferenceLibrary:
    root = root.resolve()
    records_by_path = {Path(item.path).resolve(): item for item in (existing.psarcs if existing else [])}
    tones_by_path: dict[Path, list[LocalToneReference]] = {}
    if existing:
        for tone in existing.tones:
            tones_by_path.setdefault(Path(tone.source_path).resolve(), []).append(tone)

    for path, source_type, tones in extracted:
        resolved = path.resolve()
        stat = resolved.stat()
        digest = sha256_file(resolved)
        normalized = [
            tone.model_copy(update={
                "source_psarc_sha256": digest,
                "source_path": str(resolved),
                "source_type": source_type,
            })
            for tone in tones
        ]
        records_by_path[resolved] = ScannedPsarcRecord(
            path=str(resolved),
            sha256=digest,
            size_bytes=stat.st_size,
            modified_ns=stat.st_mtime_ns,
            source_type=source_type,
            tone_count=len(normalized),
        )
        tones_by_path[resolved] = normalized

    discovered = {item.resolve() for item in discover_psarcs(root)}
    records = [record for path, record in records_by_path.items() if path in discovered]
    tones = [tone for path, items in tones_by_path.items() if path in discovered for tone in items]
    records.sort(key=lambda item: item.path.casefold())
    tones.sort(key=lambda item: (item.source_type, item.artist or "", item.title or "", item.arrangement, item.tone_key))
    return ToneReferenceLibrary(scan_root=str(root), psarcs=records, tones=tones)


def write_library(library: ToneReferenceLibrary, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(library.model_dump_json(indent=2), encoding="utf-8")
    return destination


def read_library(path: Path) -> ToneReferenceLibrary:
    return ToneReferenceLibrary.model_validate_json(path.read_text(encoding="utf-8"))
