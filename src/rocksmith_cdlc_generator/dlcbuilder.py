from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any

from .arrangement_gate import configured_arrangement_roles, require_configured_arrangements_ready
from .ffmpeg import create_preview_audio
from .fret_mapping import read_bass_mapping
from .guitar_authoring import GuitarAuthoringChart
from .metadata_integration import resolve_build_metadata
from .models import ProjectManifest
from .rocksmith_xml import rocksmith_guitar_tuning_offsets, rocksmith_tuning_offsets

_NAMESPACE = uuid.UUID("f3d544d7-8a9a-4aa0-9f19-81421769a6fd")

_ARRANGEMENT_CODES = {
    "lead": (0, 1, "guitar"),
    "rhythm": (2, 2, "guitar"),
    "bass": (3, 4, "bass"),
}


def _sanitize_key(value: str) -> str:
    key = re.sub(r"[^A-Za-z0-9]+", "", value)
    if not key:
        raise ValueError("DLC key must contain at least one alphanumeric character")
    return key[:48]


def _stable_master_id(source_sha256: str, arrangement: str) -> int:
    digest = hashlib.sha256(f"{source_sha256}:{arrangement}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def _stable_persistent_id(source_sha256: str, arrangement: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, f"{source_sha256}:{arrangement}"))


def _instrumental_fields(
    manifest: ProjectManifest,
    *,
    arrangement: str,
    xml_path: str,
    tuning_offsets: tuple[int, int, int, int, int, int],
) -> dict[str, Any]:
    if arrangement not in _ARRANGEMENT_CODES:
        raise ValueError(f"Unsupported DLC Builder arrangement: {arrangement}")
    name, route_mask, base_tone = _ARRANGEMENT_CODES[arrangement]
    return {
        "XML": xml_path,
        "Name": name,
        "RouteMask": route_mask,
        "Priority": 0,
        "ScrollSpeed": 1.3,
        "BassPicked": False,
        "Tuning": list(tuning_offsets),
        "TuningPitch": 440.0,
        "BaseTone": base_tone,
        "Tones": [],
        "MasterID": _stable_master_id(manifest.source_sha256, arrangement),
        "PersistentID": _stable_persistent_id(manifest.source_sha256, arrangement),
    }


def build_dlcbuilder_project(
    manifest: ProjectManifest,
    *,
    audio_path: str,
    preview_path: str,
    album_art_path: str,
    album_name: str,
    year: int,
    arrangements: dict[str, tuple[str, tuple[int, int, int, int, int, int]]] | None = None,
    xml_path: str | None = None,
    tuning_offsets: tuple[int, int, int, int, int, int] | None = None,
    preview_start_seconds: float = 30.0,
    dlc_key: str | None = None,
) -> dict[str, Any]:
    """Build a DLC Builder project for one or more validated arrangements.

    ``xml_path`` + ``tuning_offsets`` remain as a backward-compatible Bass-only
    shortcut for callers created before multi-arrangement support.
    """
    if not manifest.artist:
        raise ValueError("Artist metadata is required for DLC Builder export")
    if not album_name.strip():
        raise ValueError("Album name is required for DLC Builder export")
    if year < 1900 or year > 2100:
        raise ValueError("Year must be between 1900 and 2100")
    if preview_start_seconds < 0:
        raise ValueError("Preview start must be non-negative")

    if arrangements is None:
        if xml_path is None or tuning_offsets is None:
            raise ValueError("At least one arrangement is required for DLC Builder export")
        arrangements = {"bass": (xml_path, tuning_offsets)}
    if not arrangements:
        raise ValueError("At least one arrangement is required for DLC Builder export")

    key = _sanitize_key(dlc_key or f"{manifest.artist}{manifest.title}")
    payload_arrangements = []
    for role in ("lead", "rhythm", "bass"):
        if role not in arrangements:
            continue
        role_xml, role_tuning = arrangements[role]
        payload_arrangements.append(
            {
                "Case": "Instrumental",
                "Fields": [
                    _instrumental_fields(
                        manifest,
                        arrangement=role,
                        xml_path=role_xml,
                        tuning_offsets=role_tuning,
                    )
                ],
            }
        )

    unknown = sorted(set(arrangements) - set(_ARRANGEMENT_CODES))
    if unknown:
        raise ValueError(f"Unsupported DLC Builder arrangement(s): {', '.join(unknown)}")

    return {
        "Version": "1",
        "DLCKey": key,
        "ArtistName": {"Value": manifest.artist, "SortValue": manifest.artist},
        "Title": {"Value": manifest.title, "SortValue": manifest.title},
        "AlbumName": {"Value": album_name, "SortValue": album_name},
        "Year": year,
        "AlbumArtFile": album_art_path,
        "AudioFile": {"Path": audio_path, "Volume": 0.0},
        "AudioPreviewFile": {"Path": preview_path, "Volume": 0.0},
        "AudioPreviewStartTime": preview_start_seconds,
        "Arrangements": payload_arrangements,
        "Tones": [],
    }


def prepare_dlcbuilder_project(
    project_dir: Path,
    *,
    album_name: str | None,
    year: int | None,
    cover: Path,
    preview: Path | None = None,
    preview_start_seconds: float = 30.0,
    dlc_key: str | None = None,
) -> Path:
    project_dir = project_dir.resolve()
    require_configured_arrangements_ready(project_dir)

    audio = project_dir / "audio" / "normalized.wav"
    if not audio.is_file():
        raise FileNotFoundError(f"Normalized audio not found: {audio}")
    if not cover.is_file():
        raise FileNotFoundError(f"Album art not found: {cover}")

    manifest = ProjectManifest.load(project_dir)
    if preview_start_seconds >= manifest.source_metadata.duration_seconds:
        raise ValueError("Preview start must occur before the end of the song")

    resolved_metadata = resolve_build_metadata(
        project_dir,
        album_name=album_name,
        year=year,
    )

    arrangement_inputs: dict[str, tuple[Path, tuple[int, int, int, int, int, int]]] = {}
    for role in configured_arrangement_roles(project_dir):
        xml = project_dir / "eof" / f"arr_{role}_RS2.xml"
        if not xml.is_file():
            raise FileNotFoundError(
                f"Rocksmith {role.capitalize()} XML not found: {xml}. "
                f"Run `cdlc export PROJECT --instrument {role}` first."
            )
        if role == "bass":
            mapping = read_bass_mapping(project_dir / "charts" / "bass_mapped.json")
            offsets = rocksmith_tuning_offsets(mapping)
        else:
            chart_path = project_dir / "charts" / f"{role}_source.json"
            chart = GuitarAuthoringChart.model_validate_json(chart_path.read_text(encoding="utf-8"))
            offsets = rocksmith_guitar_tuning_offsets(chart)
        arrangement_inputs[role] = (xml, offsets)

    out_dir = project_dir / "build" / "dlcbuilder"
    out_dir.mkdir(parents=True, exist_ok=True)

    if preview is None:
        preview = out_dir / "preview.wav"
        remaining = manifest.source_metadata.duration_seconds - preview_start_seconds
        create_preview_audio(
            audio,
            preview,
            start_seconds=preview_start_seconds,
            duration_seconds=min(30.0, remaining),
        )
    elif not preview.is_file():
        raise FileNotFoundError(f"Preview audio not found: {preview}")

    def rel(path: Path) -> str:
        resolved = path.resolve()
        if resolved.is_relative_to(project_dir):
            return resolved.relative_to(project_dir).as_posix()
        return str(resolved)

    project = build_dlcbuilder_project(
        manifest,
        audio_path=rel(audio),
        preview_path=rel(preview),
        album_art_path=rel(cover),
        album_name=resolved_metadata.album_name,
        year=resolved_metadata.year,
        arrangements={
            role: (rel(xml), offsets)
            for role, (xml, offsets) in arrangement_inputs.items()
        },
        preview_start_seconds=preview_start_seconds,
        dlc_key=dlc_key,
    )
    destination = out_dir / f"{project['DLCKey']}.rs2dlc"

    # DLC Builder resolves relative paths from the .rs2dlc directory.
    for field in ("AlbumArtFile",):
        value = Path(project[field])
        if not value.is_absolute():
            project[field] = Path("../..", value).as_posix()
    for field in ("AudioFile", "AudioPreviewFile"):
        value = Path(project[field]["Path"])
        if not value.is_absolute():
            project[field]["Path"] = Path("../..", value).as_posix()
    for arrangement in project["Arrangements"]:
        if arrangement.get("Case") != "Instrumental":
            continue
        for fields in arrangement.get("Fields") or []:
            xml_value = Path(fields["XML"])
            if not xml_value.is_absolute():
                fields["XML"] = Path("../..", xml_value).as_posix()

    destination.write_text(json.dumps(project, indent=2), encoding="utf-8")

    provenance_path = out_dir / "metadata_resolution.json"
    provenance_path.write_text(
        json.dumps(
            {
                "album_name": resolved_metadata.album_name,
                "year": resolved_metadata.year,
                "album_source": resolved_metadata.album_source,
                "year_source": resolved_metadata.year_source,
                "selected_metadata_path": resolved_metadata.selected_metadata_path,
                "arrangements": list(arrangement_inputs),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return destination
