from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .package_generation import invalidate_package_state

Arrangement = Literal["bass", "lead", "rhythm"]
_REQUIRED_ARRANGEMENTS = ("bass", "lead", "rhythm")


class ToneRegion(BaseModel):
    """A human-confirmed tone change beginning at an absolute song time."""

    model_config = ConfigDict(frozen=True)

    start_seconds: float = Field(ge=0.0)
    tone_label: str = Field(min_length=1)


class ArrangementToneRegions(BaseModel):
    """Default tone plus ordered change points for one Rocksmith arrangement."""

    model_config = ConfigDict(frozen=True)

    arrangement: Arrangement
    default_tone: str = Field(min_length=1)
    regions: tuple[ToneRegion, ...] = ()

    @model_validator(mode="after")
    def require_ordered_unique_changes(self) -> "ArrangementToneRegions":
        previous = -1.0
        for region in self.regions:
            if region.start_seconds <= previous:
                raise ValueError("tone-region start times must be strictly increasing")
            previous = region.start_seconds
        return self


class ProjectToneRegions(BaseModel):
    """Package-facing tone labels and change regions explicitly confirmed by a human."""

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    arrangements: tuple[ArrangementToneRegions, ...]

    @model_validator(mode="after")
    def require_three_arrangements_once(self) -> "ProjectToneRegions":
        names = tuple(item.arrangement for item in self.arrangements)
        if set(names) != set(_REQUIRED_ARRANGEMENTS) or len(names) != len(_REQUIRED_ARRANGEMENTS):
            raise ValueError("tone authority must contain bass, lead, and rhythm exactly once")
        return self


def tone_regions_path(project_dir: Path) -> Path:
    return project_dir.expanduser().resolve() / "metadata" / "tone_regions.json"


def load_tone_regions(project_dir: Path) -> ProjectToneRegions | None:
    path = tone_regions_path(project_dir)
    if not path.is_file():
        return None
    try:
        return ProjectToneRegions.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, ValidationError) as exc:
        raise ValueError(f"Tone-region authority is unreadable: {path}") from exc


def confirm_tone_regions(
    project_dir: Path,
    *,
    arrangements: tuple[ArrangementToneRegions, ...],
) -> ProjectToneRegions:
    """Publish changed tone-region authority only after invalidating stale package state.

    Reconfirming the exact same normalized authority is a no-op. Tone labels are intentionally
    human-owned here; detailed amp/effect approval remains in the existing tone-review pipeline.
    """

    project = project_dir.expanduser().resolve()
    normalized = ProjectToneRegions(arrangements=arrangements)
    current = None
    try:
        current = load_tone_regions(project)
    except (OSError, ValueError):
        current = None
    if current == normalized:
        return current

    invalidate_package_state(project)
    path = tone_regions_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(normalized.model_dump_json(indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return normalized
