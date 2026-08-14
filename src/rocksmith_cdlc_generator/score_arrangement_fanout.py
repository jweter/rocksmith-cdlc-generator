from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .guitarpro_import import import_project_guitarpro
from .musicxml_import import import_project_musicxml
from .project_source_inventory import build_project_source_inventory
from .score_mapping_review import load_score_for_mapping_review
from .score_source import ArrangementRole, ProjectScoreSource
from .source_import import ImportedSource


class ConfirmedScoreArrangement(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: ArrangementRole
    source_track_index: int
    output_json: str


class ConfirmedScoreArrangementManifest(BaseModel):
    """Authority marker for normalized arrangements derived from one reviewed score."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    source_filename: str
    source_sha256: str
    source_format: str
    arrangements: list[ConfirmedScoreArrangement]


class ScoreArrangementFanoutResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_path: str
    source_sha256: str
    arrangements: dict[ArrangementRole, str]
    manifest_path: str


def _project_relative(project: Path, path: Path) -> str:
    resolved_project = project.resolve()
    resolved_path = path.resolve()
    try:
        return resolved_path.relative_to(resolved_project).as_posix()
    except ValueError as exc:
        raise ValueError(f"Imported arrangement output escaped project directory: {resolved_path}") from exc


def _registered_score_rights_are_resolved(project: Path, score: ProjectScoreSource) -> bool:
    inventory = build_project_source_inventory(project)
    matching = [
        item
        for item in inventory.local_sources
        if item.source_sha256.lower() == score.source_sha256.lower()
        and item.route_action == "register_score_source"
    ]
    return bool(matching) and all(not item.human_rights_review_required for item in matching)


def _confirmed_mapping_snapshot(score: ProjectScoreSource) -> tuple[tuple[str, int], ...]:
    return tuple(
        sorted(
            (mapping.role.value, mapping.source_track_index)
            for mapping in score.arrangement_mappings
            if mapping.human_confirmed
        )
    )


def _manifest_path(project: Path, source_sha256: str) -> Path:
    return project / "sources" / "imported" / f"score-arrangements-{source_sha256[:12]}.json"


def _import_one(
    project: Path,
    source_path: Path,
    score: ProjectScoreSource,
    *,
    role: ArrangementRole,
    source_track_index: int,
) -> Path:
    if score.source_format in {"gp3", "gp4", "gp5"}:
        return import_project_guitarpro(
            project,
            source_path,
            track_index=source_track_index,
            instrument=role.value,
        )
    if score.source_format in {"musicxml", "mxl"}:
        return import_project_musicxml(
            project,
            source_path,
            part_index=source_track_index,
            instrument=role.value,
        )
    raise ValueError(f"Confirmed score fan-out does not support {score.source_format!r}")


def _validate_output(
    output_path: Path,
    *,
    score: ProjectScoreSource,
    role: ArrangementRole,
    source_track_index: int,
) -> None:
    imported = ImportedSource.read_json(output_path)
    if imported.provenance.source_sha256.lower() != score.source_sha256.lower():
        raise ValueError("Imported arrangement provenance does not match the registered score hash")
    if len(imported.tracks) != 1:
        raise ValueError("Confirmed score arrangement import must contain exactly one normalized track")
    track = imported.tracks[0]
    if track.instrument != role.value or track.source_track_index != source_track_index:
        raise ValueError(
            "Imported arrangement does not match the human-confirmed role and score track"
        )


def import_confirmed_score_arrangements(project: Path) -> ScoreArrangementFanoutResult:
    """Materialize human-confirmed score mappings into arrangement-specific imports.

    Score role confidence is never authority here: only mappings already marked as
    explicitly human-confirmed are imported. The registered score's source-rights gate
    must also be resolved independently. A project-level manifest is published only
    after every selected output is validated against the immutable score SHA-256, exact
    source track index, and intended Bass/Lead/Rhythm role.
    """

    project = project.expanduser().resolve()
    score = load_score_for_mapping_review(project)
    if not _registered_score_rights_are_resolved(project, score):
        raise PermissionError(
            "Registered score rights/provenance review is unresolved; use cdlc-source-rights first"
        )

    confirmed = sorted(
        (mapping for mapping in score.arrangement_mappings if mapping.human_confirmed),
        key=lambda mapping: mapping.role.value,
    )
    if not confirmed:
        raise ValueError(
            "Registered score has no human-confirmed arrangement mappings; use cdlc-score-map first"
        )
    mapping_snapshot = _confirmed_mapping_snapshot(score)

    source_path = (project / score.imported_relative_path).resolve()
    manifest_path = _manifest_path(project, score.source_sha256)
    # The manifest is the authority marker. Remove an older marker before any fallible
    # re-import can overwrite one of its referenced outputs.
    manifest_path.unlink(missing_ok=True)

    outputs: dict[ArrangementRole, str] = {}
    entries: list[ConfirmedScoreArrangement] = []
    for mapping in confirmed:
        output_path = _import_one(
            project,
            source_path,
            score,
            role=mapping.role,
            source_track_index=mapping.source_track_index,
        ).resolve()
        _validate_output(
            output_path,
            score=score,
            role=mapping.role,
            source_track_index=mapping.source_track_index,
        )
        relative_output = _project_relative(project, output_path)
        outputs[mapping.role] = str(output_path)
        entries.append(
            ConfirmedScoreArrangement(
                role=mapping.role,
                source_track_index=mapping.source_track_index,
                output_json=relative_output,
            )
        )

    # Re-read and re-verify the registered score after the fallible importer calls so
    # concurrent source replacement or human remapping cannot be bound into a stale
    # authoritative manifest.
    final_score = load_score_for_mapping_review(project)
    if final_score.source_sha256 != score.source_sha256:
        raise IOError("Registered score identity changed during arrangement fan-out")
    if _confirmed_mapping_snapshot(final_score) != mapping_snapshot:
        raise RuntimeError("Human-confirmed score mappings changed during arrangement fan-out")

    manifest = ConfirmedScoreArrangementManifest(
        source_filename=score.source_filename,
        source_sha256=score.source_sha256,
        source_format=score.source_format,
        arrangements=entries,
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")

    return ScoreArrangementFanoutResult(
        project_path=str(project),
        source_sha256=score.source_sha256,
        arrangements=outputs,
        manifest_path=str(manifest_path),
    )
