from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from .arrangement_gate import require_configured_arrangements_ready
from .hashing import sha256_file


class BuildAsset(BaseModel):
    role: str
    path: str
    size_bytes: int = Field(ge=0)
    sha256: str


class BuildStageManifest(BaseModel):
    schema_version: int = 2
    validation_status: str
    dlcbuilder_project: str
    dlcbuilder_project_sha256: str
    assets: list[BuildAsset]
    safe_for_manual_packaging: bool = True
    writes_to_live_rocksmith_install: bool = False


class PsarcHeaderInfo(BaseModel):
    magic: str = "PSAR"
    version_major: int
    version_minor: int
    compression_method: str
    toc_length: int
    toc_entry_size: int
    toc_entry_count: int
    block_size_alloc: int
    archive_flags: int
    encrypted: bool


class PsarcReceipt(BaseModel):
    schema_version: int = 2
    source_path: str
    staged_path: str
    size_bytes: int = Field(gt=0)
    sha256: str
    header: PsarcHeaderInfo
    build_readiness_path: str
    build_readiness_sha256: str
    dlcbuilder_project_sha256: str
    input_assets: list[BuildAsset]
    basic_integrity: str = "PASS"
    staged_inputs_unchanged: bool = True
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

    assets = [
        _resolve_reference(base_dir, payload.get("AudioFile", {}).get("Path", ""), "song_audio"),
        _resolve_reference(base_dir, payload.get("AudioPreviewFile", {}).get("Path", ""), "preview_audio"),
        _resolve_reference(base_dir, payload.get("AlbumArtFile", ""), "album_art"),
    ]

    role_by_name = {0: "lead_xml", 2: "rhythm_xml", 3: "bass_xml"}
    seen_roles: set[str] = set()
    for arrangement in payload.get("Arrangements") or []:
        if arrangement.get("Case") != "Instrumental":
            continue
        for fields in arrangement.get("Fields") or []:
            name = fields.get("Name")
            role = role_by_name.get(name)
            if role is None:
                continue
            if role in seen_roles:
                raise ValueError(f"DLC Builder project contains duplicate {role} arrangements")
            assets.append(_resolve_reference(base_dir, fields.get("XML", ""), role))
            seen_roles.add(role)

    if not seen_roles:
        raise ValueError("DLC Builder project does not contain a supported instrumental arrangement")
    return assets


def stage_build(project_dir: Path, *, dlcbuilder_project: Path | None = None) -> Path:
    project_dir = project_dir.resolve()
    validation = require_configured_arrangements_ready(project_dir)
    rs2dlc = _find_dlcbuilder_project(project_dir, dlcbuilder_project)
    assets = inspect_dlcbuilder_assets(rs2dlc)

    stage_dir = project_dir / "build" / "staging"
    stage_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = stage_dir / "build_readiness.json"
    instructions_path = stage_dir / "BUILD_INSTRUCTIONS.md"

    manifest = BuildStageManifest(
        validation_status=validation.status,
        dlcbuilder_project=str(rs2dlc),
        dlcbuilder_project_sha256=sha256_file(rs2dlc),
        assets=assets,
    )
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    instructions_path.write_text(
        "# Manual Packaging Gate\n\n"
        "All referenced DLC Builder assets and configured arrangements exist and have been hashed.\n\n"
        "1. Open the `.rs2dlc` file in DLC Builder.\n"
        "2. Review metadata, every arrangement, tuning, artwork, and audio.\n"
        "3. Build the PC package into a location outside the live Rocksmith installation.\n"
        "4. Do not edit the staged `.rs2dlc`, XML, audio, preview, or artwork after this point.\n"
        "5. Run `cdlc register-psarc PROJECT --psarc PATH_TO_BUILT_PSARC`.\n"
        "6. Registration re-hashes every staged input and refuses the PSARC if anything changed.\n"
        "7. Inspect the generated PSARC receipt before any installation.\n"
        "8. Only then should a human deliberately copy the package into Rocksmith.\n\n"
        "This generator never writes to the live Rocksmith installation during staging or registration.\n",
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


def _read_psarc_header(path: Path) -> PsarcHeaderInfo:
    with path.open("rb") as handle:
        header = handle.read(32)
    if len(header) < 32:
        raise ValueError("PSARC is too small to contain the required 32-byte header")
    if header[:4] != b"PSAR":
        raise ValueError("PSARC header magic check failed; expected 'PSAR'")

    compression = header[8:12].decode("ascii", errors="replace")
    if compression != "zlib":
        raise ValueError("Unsupported PSARC compression header; expected 'zlib'")

    major = int.from_bytes(header[4:6], "big")
    minor = int.from_bytes(header[6:8], "big")
    if (major, minor) != (1, 4):
        raise ValueError(f"Unsupported PSARC version {major}.{minor}; expected 1.4")

    toc_length = int.from_bytes(header[12:16], "big")
    toc_entry_size = int.from_bytes(header[16:20], "big")
    toc_entry_count = int.from_bytes(header[20:24], "big")
    block_size_alloc = int.from_bytes(header[24:28], "big")
    archive_flags = int.from_bytes(header[28:32], "big")
    if toc_length < 32:
        raise ValueError("PSARC ToC length is smaller than the 32-byte header")
    if toc_entry_size <= 0:
        raise ValueError("PSARC ToC entry size must be positive")
    if block_size_alloc <= 0:
        raise ValueError("PSARC block allocation size must be positive")

    return PsarcHeaderInfo(
        version_major=major,
        version_minor=minor,
        compression_method=compression,
        toc_length=toc_length,
        toc_entry_size=toc_entry_size,
        toc_entry_count=toc_entry_count,
        block_size_alloc=block_size_alloc,
        archive_flags=archive_flags,
        encrypted=archive_flags == 4,
    )


def _load_and_verify_build_readiness(project_dir: Path) -> tuple[Path, BuildStageManifest]:
    readiness_path = project_dir / "build" / "staging" / "build_readiness.json"
    if not readiness_path.is_file():
        raise FileNotFoundError(
            "Build readiness manifest not found. Run `cdlc stage-build PROJECT` or "
            "`cdlc launch-dlcbuilder PROJECT ...` before registering a PSARC."
        )

    manifest = BuildStageManifest.model_validate_json(readiness_path.read_text(encoding="utf-8"))
    rs2dlc = Path(manifest.dlcbuilder_project).resolve()
    if not rs2dlc.is_file():
        raise FileNotFoundError(f"Staged DLC Builder project no longer exists: {rs2dlc}")
    if sha256_file(rs2dlc) != manifest.dlcbuilder_project_sha256:
        raise ValueError("DLC Builder project changed after staging; rerun `cdlc stage-build`.")

    expected = {asset.role: asset for asset in manifest.assets}
    current = {asset.role: asset for asset in inspect_dlcbuilder_assets(rs2dlc)}
    if set(current) != set(expected):
        raise ValueError("DLC Builder input set changed after staging; rerun `cdlc stage-build`.")
    for role, staged in expected.items():
        actual = current[role]
        if (
            actual.path != staged.path
            or actual.size_bytes != staged.size_bytes
            or actual.sha256 != staged.sha256
        ):
            raise ValueError(
                f"Staged input '{role}' changed after staging; rerun `cdlc stage-build`."
            )
    return readiness_path, manifest


def register_psarc(project_dir: Path, psarc: Path) -> Path:
    project_dir = project_dir.resolve()
    require_configured_arrangements_ready(project_dir)
    readiness_path, readiness = _load_and_verify_build_readiness(project_dir)

    source = psarc.resolve()
    if source.suffix.lower() != ".psarc":
        raise ValueError("Built package must have a .psarc extension")
    if not source.is_file():
        raise FileNotFoundError(f"PSARC not found: {source}")
    if source.stat().st_size <= 0:
        raise ValueError("PSARC is empty")
    header = _read_psarc_header(source)
    source_sha256 = sha256_file(source)

    stage_dir = project_dir / "build" / "staging" / "psarc"
    stage_dir.mkdir(parents=True, exist_ok=True)
    destination = stage_dir / source.name
    if source != destination.resolve():
        shutil.copy2(source, destination)
    staged_sha256 = sha256_file(destination)
    if staged_sha256 != source_sha256:
        raise ValueError("PSARC staged-copy hash does not match the source package")

    receipt = PsarcReceipt(
        source_path=str(source),
        staged_path=str(destination.resolve()),
        size_bytes=destination.stat().st_size,
        sha256=staged_sha256,
        header=header,
        build_readiness_path=str(readiness_path.resolve()),
        build_readiness_sha256=sha256_file(readiness_path),
        dlcbuilder_project_sha256=readiness.dlcbuilder_project_sha256,
        input_assets=readiness.assets,
    )
    receipt_path = project_dir / "build" / "staging" / "psarc_receipt.json"
    receipt_path.write_text(receipt.model_dump_json(indent=2), encoding="utf-8")
    return receipt_path
