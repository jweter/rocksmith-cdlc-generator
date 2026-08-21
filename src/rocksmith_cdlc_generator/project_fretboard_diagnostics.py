from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .fretboard_candidate_inventory import (
    FretboardCandidateInventory,
    build_fretboard_candidate_inventory,
)
from .score_fanout import ScoreFanoutManifest
from .score_mapping_review import load_score_for_mapping_review, score_mapping_transaction
from .score_source import ArrangementRole
from .source_import import ImportedSource

ArrangementRoleName = Literal["bass", "lead", "rhythm"]


class ProjectFretboardDiagnostic(BaseModel):
    """Read-only fretboard-position diagnostic for one current project arrangement."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    arrangement: ArrangementRole
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_track_index: int = Field(ge=0)
    output_json: str
    inventory: FretboardCandidateInventory


def _project(project_dir: Path) -> Path:
    project = project_dir.expanduser().resolve()
    if not (project / "project.json").is_file():
        raise FileNotFoundError(f"Not a CDLC project: {project}")
    return project


def _build_locked(
    project: Path,
    *,
    arrangement: ArrangementRoleName,
    max_fret: int,
) -> ProjectFretboardDiagnostic:
    score = load_score_for_mapping_review(project)
    role = ArrangementRole(arrangement)
    mapping = score.mapping_for(role)
    if mapping is None or not mapping.human_confirmed:
        raise ValueError(f"{arrangement} score mapping is not human-confirmed")

    manifest_path = (
        project
        / "sources"
        / "imported"
        / f"score-fanout-{score.source_sha256[:12]}.json"
    )
    if not manifest_path.is_file():
        raise FileNotFoundError("Current score fan-out manifest is not available")
    manifest = ScoreFanoutManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    if (
        manifest.score_source_sha256 != score.source_sha256
        or manifest.score_source_format != score.source_format
    ):
        raise ValueError("Current score fan-out does not match the registered score")

    entries = [entry for entry in manifest.arrangements if entry.role == role]
    if len(entries) != 1:
        raise ValueError(
            f"Current score fan-out must contain exactly one {arrangement} arrangement"
        )
    entry = entries[0]
    if entry.source_track_index != mapping.source_track_index:
        raise ValueError(
            f"{arrangement} fan-out does not match the human-confirmed score track"
        )

    output = (project / entry.output_json).resolve()
    if not output.is_relative_to(project) or not output.is_file():
        raise ValueError(f"{arrangement} fan-out output is not a safe project-local file")
    imported = ImportedSource.read_json(output)
    if imported.provenance.source_sha256 != score.source_sha256:
        raise ValueError(
            f"{arrangement} fan-out provenance does not match the registered score"
        )
    if len(imported.tracks) != 1:
        raise ValueError(f"{arrangement} fan-out must contain exactly one source track")
    track = imported.tracks[0]
    if track.source_track_index != entry.source_track_index or track.instrument != arrangement:
        raise ValueError(f"{arrangement} fan-out output no longer matches current authority")

    inventory = build_fretboard_candidate_inventory(
        imported,
        source_track_index=entry.source_track_index,
        max_fret=max_fret,
    )
    return ProjectFretboardDiagnostic(
        arrangement=role,
        score_sha256=score.source_sha256,
        source_track_index=entry.source_track_index,
        output_json=output.relative_to(project).as_posix(),
        inventory=inventory,
    )


def build_project_fretboard_diagnostic(
    project_dir: Path,
    *,
    arrangement: ArrangementRoleName,
    max_fret: int = 24,
) -> ProjectFretboardDiagnostic:
    """Inspect current fan-out without choosing or changing fingering.

    The diagnostic is bound to the current registered score, confirmed role mapping,
    and fan-out manifest/output. Any stale or mismatched authority fails closed before
    the pitch-correct candidate inventory is built. Reads share the score-mapping
    transaction so a concurrent mapping/fan-out update cannot produce a mixed snapshot.
    """

    project = _project(project_dir)
    with score_mapping_transaction(project):
        return _build_locked(project, arrangement=arrangement, max_fret=max_fret)
