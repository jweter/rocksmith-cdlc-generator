from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any

from .ffmpeg import create_preview_audio
from .fret_mapping import read_bass_mapping
from .metadata_integration import resolve_build_metadata
from .models import ProjectManifest
from .packaging_gate import require_packaging_ready
from .rocksmith_xml import rocksmith_tuning_offsets

_NAMESPACE = uuid.UUID("f3d544d7-8a9a-4aa0-9f19-81421769a6fd")


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


def build_dlcbuilder_project(
    manifest: ProjectManifest,
    *,
    xml_path: str,
    audio_path: str,
    preview_path: str,
    album_art_path: str,
    album_name: str,
    year: int,
    tuning_offsets: tuple[int, int, int, int, int, int],
    preview_start_seconds: float = 30.0,
    dlc_key: str | None = None,
) -> dict[str, Any]:
    if not manifest.artist:
        raise ValueError("Artist metadata is required for DLC Builder export")
    if not album_name.strip():
        raise ValueError("Album name is required for DLC Builder export")
    if year < 1900 or year > 2100:
        raise ValueError("Year must be between 1900 and 2100")
    if preview_start_seconds < 0:
        raise ValueError("Preview start must be non-negative")

    key = _sanitize_key(dlc_key or f"{manifest.artist}{manifest.title}")
    master_id = _stable_master_id(manifest.source_sha256, "bass")
    persistent_id = _stable_persistent_id(manifest.source_sha256, "bass")

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
        "Arrangements": [
            {
                "Case": "Instrumental",
                "Fields": [
                    {
                        "XML": xml_path,
                        "Name": 3,
                        "RouteMask": 4,
                        "Priority": 0,
                        "ScrollSpeed": 1.3,
                        "BassPicked": False,
                        "Tuning": list(tuning_offsets),
                        "TuningPitch": 440.0,
                        "BaseTone": "bass",
                        "Tones": [],
                        "MasterID": master_id,
                        "PersistentID": persistent_id,
                    }
                ],
            }
        ],
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
    require_packaging_ready(project_dir)

    xml = project_dir / "eof" / "arr_bass_RS2.xml"
    audio = project_dir / "audio" / "normalized.wav"
    mapping_path = project_dir / "charts" / "bass_mapped.json"
    if not xml.is_file():
        raise FileNotFoundError(f"Rocksmith XML not found: {xml}. Run `cdlc export` first.")
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

    mapping = read_bass_mapping(mapping_path)
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
        xml_path=rel(xml),
        audio_path=rel(audio),
        preview_path=rel(preview),
        album_art_path=rel(cover),
        album_name=resolved_metadata.album_name,
        year=resolved_metadata.year,
        tuning_offsets=rocksmith_tuning_offsets(mapping),
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
    xml_value = Path(project["Arrangements"][0]["Fields"][0]["XML"])
    if not xml_value.is_absolute():
        project["Arrangements"][0]["Fields"][0]["XML"] = Path("../..", xml_value).as_posix()

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
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return destination
