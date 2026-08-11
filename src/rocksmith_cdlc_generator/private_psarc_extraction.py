from __future__ import annotations

import json
import subprocess
from pathlib import Path

from pydantic import BaseModel

from .local_psarc_workspace import VerifiedPsarcCopy, inspection_output_dir, sha256_file
from .psarc_inspection import PsarcContentError, _inspect_command, default_bridge_path


class PrivatePsarcExtraction(BaseModel):
    schema_version: int = 1
    source_sha256: str
    verified_copy: str
    extracted_directory: str
    entry_count: int
    json_files: list[str]
    sng_files: list[str]
    tone_json_candidates: list[str]


def _extract_command(bridge_path: Path, psarc_path: Path, output_dir: Path) -> list[str]:
    command = _inspect_command(bridge_path, psarc_path)
    # _inspect_command validates bridge availability and chooses dotnet vs native exe.
    if bridge_path.suffix.lower() == ".dll":
        return [command[0], command[1], "extract", str(psarc_path), str(output_dir)]
    return [command[0], "extract", str(psarc_path), str(output_dir)]


def _contains_tone_key(value: object) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if "tone" in str(key).casefold():
                return True
            if _contains_tone_key(child):
                return True
    elif isinstance(value, list):
        return any(_contains_tone_key(item) for item in value)
    return False


def _tone_json_candidates(json_paths: list[Path]) -> list[str]:
    candidates: list[str] = []
    for path in json_paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if _contains_tone_key(payload):
            candidates.append(str(path))
    return sorted(candidates)


def extract_verified_psarc(
    verified: VerifiedPsarcCopy,
    *,
    workspace_root: Path,
    rocksmith_root: Path,
    bridge_path: Path | None = None,
) -> PrivatePsarcExtraction:
    if not verified.verified:
        raise ValueError("unverified PSARC copies cannot be extracted")
    if not verified.copy.is_file():
        raise FileNotFoundError(verified.copy)
    if sha256_file(verified.copy) != verified.source_sha256:
        raise ValueError("verified PSARC copy no longer matches its recorded SHA-256")

    output_dir = inspection_output_dir(
        verified,
        workspace_root=workspace_root,
        rocksmith_root=rocksmith_root,
    )
    bridge = bridge_path.resolve() if bridge_path is not None else default_bridge_path()
    command = _extract_command(bridge, verified.copy.resolve(), output_dir.resolve())

    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "private PSARC extraction failed").strip()
        raise PsarcContentError(detail) from exc

    try:
        payload = json.loads(completed.stdout.strip())
    except json.JSONDecodeError as exc:
        raise PsarcContentError("PSARC bridge returned invalid extraction JSON") from exc

    json_paths = [Path(path).resolve() for path in payload.get("jsonFiles") or []]
    sng_paths = [Path(path).resolve() for path in payload.get("sngFiles") or []]
    output_resolved = output_dir.resolve()
    for path in [*json_paths, *sng_paths]:
        if not path.is_relative_to(output_resolved):
            raise PsarcContentError("PSARC bridge reported an extracted path outside the private workspace")

    return PrivatePsarcExtraction(
        source_sha256=verified.source_sha256,
        verified_copy=str(verified.copy.resolve()),
        extracted_directory=str(output_resolved),
        entry_count=int(payload.get("entryCount") or 0),
        json_files=[str(path) for path in json_paths],
        sng_files=[str(path) for path in sng_paths],
        tone_json_candidates=_tone_json_candidates(json_paths),
    )
