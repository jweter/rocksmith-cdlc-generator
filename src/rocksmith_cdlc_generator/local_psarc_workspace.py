from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VerifiedPsarcCopy:
    source: Path
    copy: Path
    source_sha256: str
    copy_sha256: str

    @property
    def verified(self) -> bool:
        return self.source_sha256 == self.copy_sha256


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve()


def assert_private_destination(destination: Path, *, rocksmith_root: Path) -> None:
    destination = _resolved(destination)
    rocksmith_root = _resolved(rocksmith_root)
    if destination == rocksmith_root or destination.is_relative_to(rocksmith_root):
        raise ValueError("inspection output must never be written inside the live Rocksmith installation")


def copy_psarc_for_inspection(
    source: Path,
    *,
    workspace_root: Path,
    rocksmith_root: Path,
) -> VerifiedPsarcCopy:
    source = _resolved(source)
    workspace_root = _resolved(workspace_root)
    rocksmith_root = _resolved(rocksmith_root)

    if source.suffix.casefold() != ".psarc":
        raise ValueError("source must be a .psarc file")
    if not source.is_file():
        raise FileNotFoundError(source)
    if not source.is_relative_to(rocksmith_root):
        raise ValueError("source PSARC must live inside the configured Rocksmith installation")
    assert_private_destination(workspace_root, rocksmith_root=rocksmith_root)

    source_sha = sha256_file(source)
    destination_dir = workspace_root / "source_copies" / source_sha[:2] / source_sha
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / source.name

    if destination.is_file() and sha256_file(destination) == source_sha:
        copy_sha = source_sha
    else:
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        if temporary.exists():
            temporary.unlink()
        shutil.copy2(source, temporary)
        copy_sha = sha256_file(temporary)
        if copy_sha != source_sha:
            temporary.unlink(missing_ok=True)
            raise IOError("PSARC copy verification failed: SHA-256 mismatch")
        temporary.replace(destination)

    return VerifiedPsarcCopy(
        source=source,
        copy=destination,
        source_sha256=source_sha,
        copy_sha256=copy_sha,
    )


def inspection_output_dir(
    verified: VerifiedPsarcCopy,
    *,
    workspace_root: Path,
    rocksmith_root: Path,
) -> Path:
    if not verified.verified:
        raise ValueError("unverified PSARC copies cannot be inspected")
    assert_private_destination(workspace_root, rocksmith_root=rocksmith_root)
    destination = _resolved(workspace_root) / "extracted" / verified.source_sha256
    destination.mkdir(parents=True, exist_ok=True)
    return destination
