from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from .hashing import sha256_file
from .packaging_gate import require_packaging_ready


class BuildAsset(BaseModel):
    role: str
    path: str
    size_bytes: int = Field(ge=0)
    sha256: str


class BuildStageManifest(BaseModel):
    schema_version: int = 1
    validation_status: str
    dlcbuilder_project: str
    assets: list[BuildAsset]
    safe_for_manual_packaging: bool = True
    writes_to_live_rocksmith_install: bool = False


class PsarcReceipt(BaseModel):
    schema_version: int = 1
    source_path: str
    staged_path: str
    size_bytes: int = Field(gt=0)
    sha256: str
    magic: str = "PSAR"
    basic_integrity: str = "PASS"
    installed_to_rocksmith: bool = False


def _find_dlcbuilder_project(project_dir: Path, explicit: Path | None = None) -> Path:
    if explicit is not None:
        candidate = explicit.resolve()
        if not candidate.is_file():
            raise FileNotFoundError(f"DLC Builder project not found: {candidate}")
        return candidate

    candidates = sorted((project_dir / "build" / "dlcbuilder").glob("*.rs2dlc"))
    if not candidates:
        raise FileNotFoundError(
            "No DLC Builder project found. Run `cdlc prepare-dlcbuilder` first."
        )
    if len(candidates) > 1:
        raise ValueError(
            "Multiple .rs2dlc files exist; pass an explicit DLC Builder project path."
        )
    return candidates[0].resolve()


def _resolve_reference(base_dir: Path, value: str, role: str) -> BuildAsset:
    if not value or not str(value).strip():
        raise ValueError(f"DLC Builder project has no {role} path")
    raw = Path(value)
    path = raw if raw.is_absolute() else (base_dir / raw)
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Referenced {role} file does not exist: {path}")
    return BuildAsset(
        role=role,
        path=str(path),
        size_bytes=path.stat().st_size,
        sha256=sha256_file(path),
    )


def inspect_dlcbuilder_assets(rs2dlc_path: Path) -> list[BuildAsset]:
    payload = json.loads(rs2dlc_path.read_text(encoding="utf-8"))
    base_dir = rs2dlc_path.parent

    arrangements = payload.get("Arrangements") or []
    bass_xml: str | None = None
    for arrangement in arrangements:
        if arrangement.get("Case") != "Instrumental":
            continue
        fields = arrangement.get("Fields") or []
        if fields and fields[0].get("Name") == 3:
            bass_xml = fields[0].get("XML")
            break
    if bass_xml is None:
        raise ValueError("DLC Builder project does not contain a Bass arrangement")

    return [
        _resolve_reference(base_dir, payload.get("AudioFile", {}).get("Path", ""), "song_audio"),
        _resolve_reference(base_dir, payload.get("AudioPreviewFile", {}).get("Path", ""), "preview_audio"),
        _resolve_reference(base_dir, payload.get("AlbumArtFile", ""), "album_art"),
        _resolve_reference(base_dir, bass_xml, "bass_xml"),
    ]


def stage_build(project_dir: Path, *, dlcbuilder_project: Path | None = None) -> Path:
    project_dir = project_dir.resolve()
    validation = require_packaging_ready(project_dir)
    rs2dlc = _find_dlcbuilder_project(project_dir, dlcbuilder_project)
    assets = inspect_dlcbuilder_assets(rs2dlc)

    stage_dir = project_dir / "build" / "staging"
    stage_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = stage_dir / "build_readiness.json"
    instructions_path = stage_dir / "BUILD_INSTRUCTIONS.md"

    manifest = BuildStageManifest(
        validation_status=validation.status,
        dlcbuilder_project=str(rs2dlc),
        assets=assets,
    )
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    instructions_path.write_text(
        "# Manual Packaging Gate\n\n"
        "All referenced DLC Builder assets exist and have been hashed.\n\n"
        "1. Open the `.rs2dlc` file in DLC Builder.\n"
        "2. Review metadata, arrangement, tuning, artwork, and audio.\n"
        "3. Build the PC package into a location outside the live Rocksmith installation.\n"
        "4. Run `cdlc register-psarc PROJECT --psarc PATH_TO_BUILT_PSARC`.\n"
        "5. Inspect the generated PSARC receipt before any installation.\n"
        "6. Only then should a human deliberately copy the package into Rocksmith.\n\n"
        "This generator never writes to the live Rocksmith installation during staging.\n",
        encoding="utf-8",
    )
    return manifest_path


def launch_dlcbuilder(
    project_dir: Path,
    *,
    executable: Path,
    dlcbuilder_project: Path | None = None,
) -> Path:
    manifest_path = stage_build(project_dir, dlcbuilder_project=dlcbuilder_project)
    exe = executable.resolve()
    if not exe.is_file():
        raise FileNotFoundError(f"DLC Builder executable not found: {exe}")
    manifest = BuildStageManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    subprocess.Popen([str(exe), manifest.dlcbuilder_project])
    return manifest_path


def _verify_psarc_header(path: Path) -> None:
    with path.open("rb") as handle:
        header = handle.read(12)
    if len(header) < 12:
        raise ValueError("PSARC is too small to contain a valid header")
    if header[:4] != b"PSAR":
        raise ValueError("PSARC header magic check failed; expected 'PSAR'")
    if header[8:12] != b"zlib":
        raise ValueError("Unsupported PSARC compression header; expected 'zlib'")


def register_psarc(project_dir: Path, psarc: Path) -> Path:
    project_dir = project_dir.resolve()
    require_packaging_ready(project_dir)
    source = psarc.resolve()
    if source.suffix.lower() != ".psarc":
        raise ValueError("Built package must have a .psarc extension")
    if not source.is_file():
        raise FileNotFoundError(f"PSARC not found: {source}")
    if source.stat().st_size <= 0:
        raise ValueError("PSARC is empty")
    _verify_psarc_header(source)

    stage_dir = project_dir / "build" / "staging" / "psarc"
    stage_dir.mkdir(parents=True, exist_ok=True)
    destination = stage_dir / source.name
    if source != destination.resolve():
        shutil.copy2(source, destination)

    receipt = PsarcReceipt(
        source_path=str(source),
        staged_path=str(destination.resolve()),
        size_bytes=destination.stat().st_size,
        sha256=sha256_file(destination),
    )
    receipt_path = project_dir / "build" / "staging" / "psarc_receipt.json"
    receipt_path.write_text(receipt.model_dump_json(indent=2), encoding="utf-8")
    return receipt_path
