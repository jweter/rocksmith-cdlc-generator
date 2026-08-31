from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .ffmpeg import inspect_audio, normalize_audio
from .hashing import sha256_file
from .models import ArtifactRecord, ProjectManifest


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "project"


def create_project(*, audio: Path, projects_root: Path, artist: str | None, title: str, instruments: list[str]) -> Path:
    audio = audio.expanduser().resolve()
    if not audio.is_file():
        raise FileNotFoundError(audio)

    stem = f"{artist}-{title}" if artist else title
    project_dir = (projects_root / slugify(stem)).resolve()
    if project_dir.exists():
        raise FileExistsError(f"Project already exists: {project_dir}")

    for relative in ("source", "audio", "stems", "analysis", "charts", "review", "eof", "build"):
        (project_dir / relative).mkdir(parents=True, exist_ok=True)

    source_copy = project_dir / "source" / audio.name
    shutil.copy2(audio, source_copy)

    original_hash = sha256_file(audio)
    copied_hash = sha256_file(source_copy)
    if original_hash != copied_hash:
        shutil.rmtree(project_dir)
        raise IOError("Source copy hash mismatch; project creation aborted.")

    manifest = ProjectManifest(
        project_name=title if not artist else f"{artist} - {title}",
        artist=artist,
        title=title,
        arrangement_instruments=instruments,
        source_original_path=str(audio),
        source_project_path=source_copy.relative_to(project_dir).as_posix(),
        source_sha256=original_hash,
        source_metadata=inspect_audio(source_copy),
    )
    manifest.save(project_dir)
    return project_dir


def normalize_project(project_dir: Path) -> Path:
    project_dir = project_dir.resolve()
    manifest = ProjectManifest.load(project_dir)
    source = project_dir / manifest.source_project_path
    if sha256_file(source) != manifest.source_sha256:
        raise IOError("Project source hash changed. Refusing to normalize altered source audio.")

    destination = project_dir / "audio" / "normalized.wav"
    command = normalize_audio(source, destination)
    manifest.normalized_audio.status = "complete"
    manifest.normalized_audio.command = command
    manifest.normalized_audio.output = ArtifactRecord(
        path=destination.relative_to(project_dir).as_posix(),
        sha256=sha256_file(destination),
    )
    manifest.normalized_audio.completed_at = datetime.now(timezone.utc)
    manifest.save(project_dir)
    return destination
