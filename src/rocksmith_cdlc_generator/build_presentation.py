from __future__ import annotations

import os
import shutil
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .hashing import sha256_file
from .package_generation import invalidate_package_state

_ALLOWED_COVER_SUFFIXES = {".jpg", ".jpeg", ".png"}


class BuildPresentation(BaseModel):
    """Human-confirmed package presentation metadata bound to project-local cover bytes."""

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    album_name: str = Field(min_length=1)
    year: int = Field(ge=1900, le=2100)
    cover_path: str
    cover_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def presentation_path(project_dir: Path) -> Path:
    return project_dir.expanduser().resolve() / "metadata" / "build_presentation.json"


def _resolved_cover(project: Path, relative: str) -> Path:
    cover = (project / relative).resolve()
    if not cover.is_relative_to(project):
        raise ValueError("Build presentation cover must remain inside the project")
    return cover


def load_build_presentation(project_dir: Path) -> BuildPresentation | None:
    project = project_dir.expanduser().resolve()
    path = presentation_path(project)
    if not path.is_file():
        return None
    try:
        presentation = BuildPresentation.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, ValidationError) as exc:
        raise ValueError(f"Build presentation is unreadable: {path}") from exc

    cover = _resolved_cover(project, presentation.cover_path)
    if not cover.is_file():
        raise FileNotFoundError(f"Saved cover art is missing: {cover}")
    if sha256_file(cover) != presentation.cover_sha256:
        raise ValueError("Saved cover art no longer matches the confirmed build presentation")
    return presentation


def build_presentation_cover_path(project_dir: Path, presentation: BuildPresentation) -> Path:
    project = project_dir.expanduser().resolve()
    cover = _resolved_cover(project, presentation.cover_path)
    if not cover.is_file():
        raise FileNotFoundError(f"Saved cover art is missing: {cover}")
    if sha256_file(cover) != presentation.cover_sha256:
        raise ValueError("Saved cover art no longer matches the confirmed build presentation")
    return cover


def save_build_presentation(
    project_dir: Path,
    *,
    album_name: str,
    year: int,
    cover: Path,
) -> BuildPresentation:
    """Confirm package-facing metadata and copy cover art into the local project.

    Package generation is invalidated before publishing any changed presentation authority.
    Re-saving byte-identical cover art with the same album/year is a no-op.
    """

    project = project_dir.expanduser().resolve()
    album = album_name.strip()
    if not album:
        raise ValueError("Album name is required")
    if year < 1900 or year > 2100:
        raise ValueError("Year must be between 1900 and 2100")

    source = cover.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Cover art not found: {source}")
    suffix = source.suffix.lower()
    if suffix not in _ALLOWED_COVER_SUFFIXES:
        raise ValueError("Cover art must be a PNG or JPEG file")
    source_sha = sha256_file(source)

    current = None
    try:
        current = load_build_presentation(project)
    except (OSError, ValueError, FileNotFoundError):
        current = None
    if (
        current is not None
        and current.album_name == album
        and current.year == year
        and current.cover_sha256 == source_sha
    ):
        return current

    # Presentation metadata affects the package itself. Advance package authority first so
    # any failure during replacement can only leave old package state invalid, never current.
    invalidate_package_state(project)

    assets = project / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    destination = assets / f"cover{suffix}"
    temporary_cover = destination.with_name(destination.name + ".tmp")
    shutil.copyfile(source, temporary_cover)
    os.replace(temporary_cover, destination)

    # Keep only the currently confirmed cover copy. These are private project bytes, not
    # repository fixtures or redistributable assets.
    for stale in assets.glob("cover.*"):
        if stale != destination and stale.is_file():
            stale.unlink()

    presentation = BuildPresentation(
        album_name=album,
        year=year,
        cover_path=destination.relative_to(project).as_posix(),
        cover_sha256=source_sha,
    )
    path = presentation_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_json = path.with_name(path.name + ".tmp")
    temporary_json.write_text(presentation.model_dump_json(indent=2) + "\n", encoding="utf-8")
    os.replace(temporary_json, path)
    return presentation
