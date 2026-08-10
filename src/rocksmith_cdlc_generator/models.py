from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class AudioMetadata(BaseModel):
    duration_seconds: float
    sample_rate_hz: int
    channels: int
    codec_name: str | None = None
    format_name: str | None = None


class ArtifactRecord(BaseModel):
    path: str
    sha256: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StageRecord(BaseModel):
    status: Literal["pending", "complete", "failed"] = "pending"
    command: list[str] | None = None
    output: ArtifactRecord | None = None
    message: str | None = None
    completed_at: datetime | None = None


class ProjectManifest(BaseModel):
    schema_version: int = 1
    project_name: str
    artist: str | None = None
    title: str
    arrangement_instruments: list[str] = Field(default_factory=lambda: ["bass"])
    target_game: str = "Rocksmith 2014 Remastered"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_original_path: str
    source_project_path: str
    source_sha256: str
    source_metadata: AudioMetadata
    normalized_audio: StageRecord = Field(default_factory=StageRecord)

    def save(self, project_dir: Path) -> None:
        (project_dir / "project.json").write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, project_dir: Path) -> "ProjectManifest":
        return cls.model_validate_json((project_dir / "project.json").read_text(encoding="utf-8"))
