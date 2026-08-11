from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .tone_reference_library import ArrangementRole, LocalToneReference, ToneReferenceLibrary


@dataclass(frozen=True)
class ToneCorpusStats:
    psarc_count: int
    tone_count: int
    official_tone_count: int
    source_counts: dict[str, int]
    arrangement_counts: dict[str, int]
    unique_fingerprint_count: int
    duplicate_tone_count: int
    device_key_counts: dict[str, int]
    descriptor_counts: dict[str, int]


@dataclass(frozen=True)
class ToneMatchDiagnostic:
    score: float
    tone: LocalToneReference
    authority_weight: float
    key_overlap: float
    descriptor_overlap: float
    matched_device_keys: tuple[str, ...]
    matched_descriptors: tuple[str, ...]


def summarize_library(library: ToneReferenceLibrary) -> ToneCorpusStats:
    source_counts = Counter(tone.source_type for tone in library.tones)
    arrangement_counts = Counter(tone.arrangement for tone in library.tones)
    fingerprint_counts = Counter(tone.fingerprint for tone in library.tones)
    device_key_counts = Counter(
        component.device_key
        for tone in library.tones
        for component in tone.components
        if component.device_key
    )
    descriptor_counts = Counter(
        descriptor.casefold()
        for tone in library.tones
        for descriptor in tone.tone_descriptors
        if descriptor.strip()
    )
    unique_fingerprint_count = len(fingerprint_counts)
    duplicate_tone_count = sum(count - 1 for count in fingerprint_counts.values() if count > 1)
    return ToneCorpusStats(
        psarc_count=len(library.psarcs),
        tone_count=len(library.tones),
        official_tone_count=library.official_tone_count,
        source_counts=dict(sorted(source_counts.items())),
        arrangement_counts=dict(sorted(arrangement_counts.items())),
        unique_fingerprint_count=unique_fingerprint_count,
        duplicate_tone_count=duplicate_tone_count,
        device_key_counts=dict(sorted(device_key_counts.items(), key=lambda item: (-item[1], item[0].casefold()))),
        descriptor_counts=dict(sorted(descriptor_counts.items(), key=lambda item: (-item[1], item[0]))),
    )


def diagnose_similarity(
    library: ToneReferenceLibrary,
    *,
    arrangement: ArrangementRole,
    device_keys: set[str] | None = None,
    descriptors: set[str] | None = None,
    limit: int = 10,
) -> list[ToneMatchDiagnostic]:
    if limit <= 0:
        return []
    wanted_keys = {item.casefold() for item in (device_keys or set())}
    wanted_desc = {item.casefold() for item in (descriptors or set())}
    diagnostics: list[ToneMatchDiagnostic] = []
    for tone in library.tones:
        if tone.arrangement != arrangement:
            continue
        tone_keys = {item.device_key.casefold() for item in tone.components}
        tone_desc = {item.casefold() for item in tone.tone_descriptors}
        matched_keys = tuple(sorted(tone_keys & wanted_keys))
        matched_desc = tuple(sorted(tone_desc & wanted_desc))
        key_overlap = len(matched_keys) / max(1, len(wanted_keys)) if wanted_keys else 0.0
        descriptor_overlap = len(matched_desc) / max(1, len(wanted_desc)) if wanted_desc else 0.0
        score = round(
            tone.authority_weight * (0.15 + 0.65 * key_overlap + 0.20 * descriptor_overlap),
            4,
        )
        diagnostics.append(
            ToneMatchDiagnostic(
                score=score,
                tone=tone,
                authority_weight=tone.authority_weight,
                key_overlap=round(key_overlap, 4),
                descriptor_overlap=round(descriptor_overlap, 4),
                matched_device_keys=matched_keys,
                matched_descriptors=matched_desc,
            )
        )
    diagnostics.sort(
        key=lambda item: (
            -item.score,
            item.tone.artist or "",
            item.tone.title or "",
            item.tone.tone_key,
        )
    )
    return diagnostics[:limit]
