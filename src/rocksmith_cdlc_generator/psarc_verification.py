from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .hashing import sha256_file
from .psarc_import import PsarcBridgeUnavailable, _default_bridge_path


class PsarcStructureReport(BaseModel):
    schema_version: int = 1
    psarc_path: str
    sha256: str
    size_bytes: int = Field(gt=0)
    upstream_commit: str
    entry_count: int = Field(gt=0)
    bass_sng: list[str]
    manifests: list[str]
    audio_wem: list[str]
    sound_banks: list[str]
    xblocks: list[str]
    album_art: list[str]
    required_structure: str = "PASS"
    safe_for_manual_install_review: bool = True
    installed_to_rocksmith: bool = False


def validate_structure_payload(payload: dict[str, Any]) -> None:
    checks = {
        "Bass SNG": payload.get("bassSng") or [],
        "manifest JSON": payload.get("manifests") or [],
        "audio WEM": payload.get("audioWem") or [],
        "sound bank": payload.get("soundBanks") or [],
        "xblock": payload.get("xblocks") or [],
        "album art": payload.get("albumArt") or [],
    }
    missing = [label for label, entries in checks.items() if not entries]
    if missing:
        raise ValueError("PSARC is missing required Rocksmith package content: " + ", ".join(missing))
    if len(checks["xblock"]) != 1:
        raise ValueError(f"Expected exactly one xblock for a single-song package, found {len(checks['xblock'])}")


def _bridge_command(bridge: Path, psarc: Path) -> list[str]:
    if not bridge.is_file():
        raise PsarcBridgeUnavailable(
            f"PSARC bridge not found: {bridge}. Run scripts/bootstrap_psarc_bridge.ps1 first or pass --bridge."
        )
    if bridge.suffix.lower() == ".dll":
        dotnet = shutil.which("dotnet")
        if dotnet is None:
            raise PsarcBridgeUnavailable("The PSARC bridge requires .NET 10; dotnet was not found on PATH.")
        return [dotnet, str(bridge), "inspect", str(psarc)]
    return [str(bridge), "inspect", str(psarc)]


def verify_project_psarc(
    project_dir: Path,
    psarc: Path,
    *,
    bridge_path: Path | None = None,
) -> Path:
    project_dir = project_dir.resolve()
    psarc = psarc.resolve()
    if not psarc.is_file():
        raise FileNotFoundError(psarc)
    if psarc.suffix.lower() != ".psarc":
        raise ValueError("Structural verification requires a .psarc file")

    bridge = bridge_path.resolve() if bridge_path is not None else _default_bridge_path()
    try:
        completed = subprocess.run(
            _bridge_command(bridge, psarc),
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "PSARC inspection bridge failed").strip()
        raise ValueError(detail) from exc

    try:
        payload = json.loads(completed.stdout.strip())
    except json.JSONDecodeError as exc:
        raise ValueError("PSARC inspection bridge returned invalid JSON") from exc

    validate_structure_payload(payload)
    report = PsarcStructureReport(
        psarc_path=str(psarc),
        sha256=sha256_file(psarc),
        size_bytes=psarc.stat().st_size,
        upstream_commit=str(payload.get("upstreamCommit") or "unknown"),
        entry_count=int(payload.get("entryCount") or 0),
        bass_sng=list(payload.get("bassSng") or []),
        manifests=list(payload.get("manifests") or []),
        audio_wem=list(payload.get("audioWem") or []),
        sound_banks=list(payload.get("soundBanks") or []),
        xblocks=list(payload.get("xblocks") or []),
        album_art=list(payload.get("albumArt") or []),
    )
    out = project_dir / "build" / "staging" / "psarc_structure.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return out
