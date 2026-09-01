from __future__ import annotations

from pathlib import Path
import sys


BWV1007_BASS_DROPD_MANIFEST = "bwv1007_bass_dropd.yaml"


def packaged_reference_manifest(filename: str) -> Path:
    """Locate one explicitly packaged public-safe reference-set manifest.

    Development/source checkouts read the canonical file directly from `benchmarks/`.
    PyInstaller onedir builds copy the same file under `_MEIPASS/private_reference_sets`.
    No private page image is packaged here; these files contain metadata and hashes only.
    """

    if filename != BWV1007_BASS_DROPD_MANIFEST:
        raise FileNotFoundError(f"unknown packaged reference manifest: {filename}")

    candidates: list[Path] = []
    package_file = Path(__file__).resolve()
    if len(package_file.parents) >= 3:
        candidates.append(
            package_file.parents[2] / "benchmarks" / "private_reference_sets" / filename
        )

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "private_reference_sets" / filename)

    candidates.append(Path.cwd() / "benchmarks" / "private_reference_sets" / filename)

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        f"packaged reference manifest {filename!r} was not found; checked: "
        + ", ".join(str(candidate) for candidate in candidates)
    )


def bwv1007_bass_dropd_manifest_path() -> Path:
    return packaged_reference_manifest(BWV1007_BASS_DROPD_MANIFEST)
