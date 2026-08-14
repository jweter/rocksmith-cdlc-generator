from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ArrangementRole(str, Enum):
    bass = "bass"
    lead = "lead"
    rhythm = "rhythm"


class ScoreTrackCandidate(BaseModel):
    """One track/part discovered inside a project-level symbolic score source."""

    model_config = ConfigDict(frozen=True)

    source_track_index: int = Field(ge=0)
    name: str | None = None
    instrument_hint: str | None = None
    tuning_midi: list[int] | None = None
    note_count: int = Field(ge=0)


class ScoreArrangementMapping(BaseModel):
    """Proposed or human-confirmed mapping from one score track to one Rocksmith role."""

    model_config = ConfigDict(frozen=True)

    role: ArrangementRole
    source_track_index: int = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    basis: list[str] = Field(default_factory=list)
    human_confirmed: bool = False

    @property
    def requires_human_review(self) -> bool:
        """Return whether a person still needs to accept this musical source mapping.

        Confidence records how strongly the importer supports its proposal. It is
        evidence for review, not authority to accept a Bass/Lead/Rhythm assignment.
        """

        return not self.human_confirmed


class ProjectScoreSource(BaseModel):
    """Project-level contract for one complete symbolic score shared by arrangements.

    The source is registered once. Bass, Lead, and Rhythm map into tracks/parts from
    that shared score instead of re-ingesting the same file independently.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    source_filename: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_format: Literal["gp3", "gp4", "gp5", "gpif", "musicxml", "mxl", "midi"]
    imported_relative_path: str
    tracks: list[ScoreTrackCandidate]
    arrangement_mappings: list[ScoreArrangementMapping] = Field(default_factory=list)

    @model_validator(mode="after")
    def mappings_reference_known_tracks_and_unique_roles(self) -> "ProjectScoreSource":
        track_indexes = {track.source_track_index for track in self.tracks}
        if len(track_indexes) != len(self.tracks):
            raise ValueError("score source track indexes must be unique")

        seen_roles: set[ArrangementRole] = set()
        for mapping in self.arrangement_mappings:
            if mapping.source_track_index not in track_indexes:
                raise ValueError(
                    f"{mapping.role.value} mapping references unknown score track "
                    f"{mapping.source_track_index}"
                )
            if mapping.role in seen_roles:
                raise ValueError(f"score source contains multiple mappings for {mapping.role.value}")
            seen_roles.add(mapping.role)
        return self

    def mapping_for(self, role: ArrangementRole) -> ScoreArrangementMapping | None:
        return next((mapping for mapping in self.arrangement_mappings if mapping.role is role), None)

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return path

    @classmethod
    def read_json(cls, path: Path) -> "ProjectScoreSource":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
