from __future__ import annotations

import os
import secrets
import shutil
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError


_INITIAL_GENERATION = "0" * 64


class PackageGeneration(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    token: str = Field(pattern=r"^[0-9a-f]{64}$")


def _generation_path(project_dir: Path) -> Path:
    return project_dir.resolve() / "build" / "package_generation.json"


def current_package_generation(project_dir: Path) -> str:
    path = _generation_path(project_dir)
    if not path.is_file():
        return _INITIAL_GENERATION
    try:
        generation = PackageGeneration.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, ValidationError) as exc:
        raise ValueError(f"Package-generation marker is unreadable: {path}") from exc
    return generation.token


def bump_package_generation(project_dir: Path) -> str:
    """Publish a new package-generation identity before invalidating downstream state."""

    project = project_dir.resolve()
    path = _generation_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(32)
    payload = PackageGeneration(token=token).model_dump_json(indent=2) + "\n"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)
    return token


def require_package_generation(project_dir: Path, expected: str) -> None:
    current = current_package_generation(project_dir)
    if current != expected:
        raise ValueError(
            "Package/chart state changed during this operation; staged package authority is stale. "
            "Rerun staging and package registration."
        )


def invalidate_package_state(project_dir: Path) -> str:
    """Advance package authority before deleting DLC Builder and PSARC staging state."""

    project = project_dir.resolve()
    token = bump_package_generation(project)
    for stale_dir in (project / "build" / "dlcbuilder", project / "build" / "staging"):
        if stale_dir.exists():
            shutil.rmtree(stale_dir)
        if stale_dir.exists():
            raise OSError(f"Failed to invalidate stale package state: {stale_dir}")
    return token
