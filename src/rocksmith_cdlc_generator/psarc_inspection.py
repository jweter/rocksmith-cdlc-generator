from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel

from .arrangement_gate import ArrangementRole, configured_arrangement_roles

_BRIDGE_COMMIT = "b87c9a3afd31c40ade9685a9244e718e7581c0cb"


class PsarcContentInspection(BaseModel):
    schema_version: int = 1
    upstream_commit: str = _BRIDGE_COMMIT
    entry_count: int
    entries: list[str]
    lead_sng: list[str]
    rhythm_sng: list[str]
    bass_sng: list[str]
    manifests: list[str]
    audio_wem: list[str]
    sound_banks: list[str]
    xblocks: list[str]
    album_art: list[str]


class PsarcContentValidation(BaseModel):
    schema_version: int = 1
    status: str
    configured_arrangements: list[ArrangementRole]
    failures: list[str]
    inspection: PsarcContentInspection


class PsarcInspectionUnavailable(RuntimeError):
    pass


class PsarcContentError(ValueError):
    pass


def default_bridge_path() -> Path:
    configured = os.environ.get("ROCKSMITH_PSARC_BRIDGE")
    if configured:
        return Path(configured).expanduser().resolve()
    return (
        Path.cwd()
        / "tools"
        / "psarc_bridge"
        / "bin"
        / "Release"
        / "net10.0"
        / "RocksmithPsarcBridge.dll"
    ).resolve()


def bridge_available(bridge_path: Path | None = None) -> bool:
    bridge = bridge_path.resolve() if bridge_path is not None else default_bridge_path()
    if not bridge.is_file():
        return False
    if bridge.suffix.lower() != ".dll":
        return True
    return shutil.which("dotnet") is not None


def _inspect_command(bridge_path: Path, psarc_path: Path) -> list[str]:
    if not bridge_path.is_file():
        raise PsarcInspectionUnavailable(
            f"PSARC bridge not found: {bridge_path}. Run scripts/bootstrap_psarc_bridge.ps1 first "
            "or set ROCKSMITH_PSARC_BRIDGE."
        )
    if bridge_path.suffix.lower() == ".dll":
        dotnet = shutil.which("dotnet")
        if dotnet is None:
            raise PsarcInspectionUnavailable(
                "PSARC content inspection requires .NET 10; dotnet was not found on PATH."
            )
        return [dotnet, str(bridge_path), "inspect", str(psarc_path)]
    return [str(bridge_path), "inspect", str(psarc_path)]


def inspect_psarc_content(
    psarc_path: Path,
    *,
    bridge_path: Path | None = None,
) -> PsarcContentInspection:
    psarc_path = psarc_path.resolve()
    if not psarc_path.is_file():
        raise FileNotFoundError(psarc_path)
    bridge = bridge_path.resolve() if bridge_path is not None else default_bridge_path()
    command = _inspect_command(bridge, psarc_path)
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "PSARC content inspection failed").strip()
        raise PsarcContentError(detail) from exc
    try:
        payload = json.loads(completed.stdout.strip())
    except json.JSONDecodeError as exc:
        raise PsarcContentError("PSARC bridge returned invalid inspection JSON") from exc

    return PsarcContentInspection(
        upstream_commit=str(payload.get("upstreamCommit") or _BRIDGE_COMMIT),
        entry_count=int(payload.get("entryCount") or 0),
        entries=list(payload.get("entries") or []),
        lead_sng=list(payload.get("leadSng") or []),
        rhythm_sng=list(payload.get("rhythmSng") or []),
        bass_sng=list(payload.get("bassSng") or []),
        manifests=list(payload.get("manifests") or []),
        audio_wem=list(payload.get("audioWem") or []),
        sound_banks=list(payload.get("soundBanks") or []),
        xblocks=list(payload.get("xblocks") or []),
        album_art=list(payload.get("albumArt") or []),
    )


def evaluate_psarc_content(
    configured_arrangements: list[ArrangementRole],
    inspection: PsarcContentInspection,
) -> PsarcContentValidation:
    failures: list[str] = []
    arrangement_entries = {
        "lead": inspection.lead_sng,
        "rhythm": inspection.rhythm_sng,
        "bass": inspection.bass_sng,
    }
    for role in configured_arrangements:
        if not arrangement_entries[role]:
            failures.append(f"Built PSARC contains no {role.capitalize()} SNG arrangement")

    if len(inspection.xblocks) != 1:
        failures.append(f"Expected exactly one xblock, found {len(inspection.xblocks)}")
    if not inspection.manifests:
        failures.append("Built PSARC contains no manifest JSON")
    if not inspection.audio_wem:
        failures.append("Built PSARC contains no WEM audio")
    if not inspection.sound_banks:
        failures.append("Built PSARC contains no sound bank")
    if not inspection.album_art:
        failures.append("Built PSARC contains no album-art DDS")
    if inspection.entry_count <= 0 or not inspection.entries:
        failures.append("Built PSARC manifest is empty")

    return PsarcContentValidation(
        status="FAIL" if failures else "PASS",
        configured_arrangements=configured_arrangements,
        failures=failures,
        inspection=inspection,
    )


def validate_project_psarc_content(
    project_dir: Path,
    psarc_path: Path,
    *,
    bridge_path: Path | None = None,
) -> PsarcContentValidation:
    roles = configured_arrangement_roles(project_dir.resolve())
    inspection = inspect_psarc_content(psarc_path, bridge_path=bridge_path)
    validation = evaluate_psarc_content(roles, inspection)
    if validation.status == "FAIL":
        raise PsarcContentError("; ".join(validation.failures))
    return validation
