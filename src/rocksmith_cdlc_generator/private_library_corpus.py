"""Private Rocksmith library regression-corpus inventory helpers.

This module deliberately handles files only on the local machine. It never uploads
source packages or extracted content. Repository-safe exports must use
``corpus_evidence_summary`` so local filenames and relative paths cannot leak.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import shutil
from typing import Iterable, Mapping


CORPUS_SCHEMA_VERSION = 1
CORPUS_EVIDENCE_SCHEMA_VERSION = 1
_ALLOWED_TIERS = {"A", "B", "C"}


@dataclass(frozen=True)
class CorpusItem:
    relative_path: str
    sha256: str
    size_bytes: int
    trust_tier: str = "C"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve()


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def validate_mirror_boundaries(source_root: Path, mirror_root: Path) -> tuple[Path, Path]:
    """Return resolved roots after proving source and mirror cannot overlap."""

    source = _resolved(source_root)
    mirror = _resolved(mirror_root)
    if source == mirror or _is_within(mirror, source) or _is_within(source, mirror):
        raise ValueError("source and private mirror must be separate, non-overlapping trees")
    if not source.is_dir():
        raise ValueError("source library must exist and be a directory")
    return source, mirror


def hash_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def mirror_inventory(
    source_root: Path,
    mirror_root: Path,
    *,
    patterns: Iterable[str] = ("*.psarc",),
    trust_tier: str = "C",
) -> dict[str, object]:
    """Copy matching packages to a private mirror and return local-only inventory.

    The returned inventory contains relative paths and is therefore private/local
    evidence. Use :func:`corpus_evidence_summary` before exporting derived evidence.
    """

    tier = trust_tier.upper()
    if tier not in _ALLOWED_TIERS:
        raise ValueError(f"trust_tier must be one of {sorted(_ALLOWED_TIERS)}")

    source, mirror = validate_mirror_boundaries(source_root, mirror_root)
    matches: set[Path] = set()
    for pattern in patterns:
        matches.update(path for path in source.rglob(pattern) if path.is_file())

    items: list[CorpusItem] = []
    for src in sorted(matches, key=lambda path: path.relative_to(source).as_posix().lower()):
        relative = src.relative_to(source)
        destination = mirror / relative
        destination.parent.mkdir(parents=True, exist_ok=True)

        source_hash = hash_file(src)
        if not destination.exists() or hash_file(destination) != source_hash:
            shutil.copy2(src, destination)
        mirrored_hash = hash_file(destination)
        if mirrored_hash != source_hash:
            raise OSError(f"mirror verification failed for {relative.as_posix()}")

        items.append(
            CorpusItem(
                relative_path=relative.as_posix(),
                sha256=source_hash,
                size_bytes=src.stat().st_size,
                trust_tier=tier,
            )
        )

    return {
        "corpus_schema_version": CORPUS_SCHEMA_VERSION,
        "item_count": len(items),
        "items": [item.to_dict() for item in items],
    }


def corpus_evidence_summary(inventory: Mapping[str, object]) -> dict[str, object]:
    """Return repository-safe derived evidence without private path disclosure.

    Item hashes bind the evidence to exact local bytes without exposing source bytes
    or filenames. Trust tiers are reported only as aggregate counts and are never
    inferred here.
    """

    raw_items = inventory.get("items")
    if not isinstance(raw_items, list):
        raise ValueError("inventory items must be a list")

    hashes: list[str] = []
    tier_counts = {tier: 0 for tier in sorted(_ALLOWED_TIERS)}
    total_bytes = 0
    for item in raw_items:
        if not isinstance(item, Mapping):
            raise ValueError("inventory item must be an object")
        digest = item.get("sha256")
        size = item.get("size_bytes")
        tier = item.get("trust_tier")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("inventory item requires a SHA-256 digest")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ValueError("inventory item requires a non-negative byte size")
        if not isinstance(tier, str) or tier.upper() not in _ALLOWED_TIERS:
            raise ValueError("inventory item requires an explicit A/B/C trust tier")
        hashes.append(digest.lower())
        total_bytes += size
        tier_counts[tier.upper()] += 1

    corpus_digest = sha256("\n".join(sorted(hashes)).encode("ascii")).hexdigest()
    return {
        "corpus_evidence_schema_version": CORPUS_EVIDENCE_SCHEMA_VERSION,
        "item_count": len(raw_items),
        "total_bytes": total_bytes,
        "trust_tier_counts": tier_counts,
        "corpus_sha256": corpus_digest,
    }
