"""Private Rocksmith library regression-corpus inventory helpers.

This module deliberately handles files only on the local machine.  It never uploads
source packages or extracted content; callers may persist only the returned,
sanitary metadata after applying the repository's provenance/privacy policy.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import shutil
from typing import Iterable


CORPUS_SCHEMA_VERSION = 1
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
    """Return resolved roots after proving source and mirror cannot overlap.

    The mirror must be outside the live library tree, and the source must not be
    inside the mirror.  This prevents accidental writes into the live game tree
    and recursive self-copying.
    """

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
    """Copy matching packages to a private mirror and return hash-only inventory.

    Unknown/custom material defaults to Tier C.  Tier A/B assignment must be an
    explicit caller decision based on reliable local evidence; this function does
    not infer musical/provenance authority from filenames or package contents.
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
