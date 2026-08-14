from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .guitarpro_import import import_project_guitarpro
from .hashing import sha256_file
from .musicxml_import import import_project_musicxml
from .project_source_inventory import build_project_source_inventory
from .reconciliation import ReconciledBassChart, SourceDisagreementReport
from .score_mapping_review import load_score_for_mapping_review, score_mapping_transaction
from .score_source import ArrangementRole, ProjectScoreSource, ScoreArrangementMapping
from .source_import import ImportedSource

_SUPPORTED_FANOUT_FORMATS = {"gp3", "gp4", "gp5", "musicxml", "mxl"}


class ScoreFanoutEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: ArrangementRole
    source_track_index: int = Field(ge=0)
    output_json: str


class ScoreFanoutManifest(BaseModel):
    """Authority marker for arrangement imports derived from one reviewed score snapshot."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    score_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_source_format: str
    arrangements: list[ScoreFanoutEntry]


class ScoreFanoutResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    manifest_path: str
    outputs: dict[str, str]


def _project(project_dir: Path) -> Path:
    project = project_dir.expanduser().resolve()
    if not (project / "project.json").is_file():
        raise FileNotFoundError(f"Not a CDLC project: {project}")
    return project


def _reviewed_score_path(project: Path, score: ProjectScoreSource) -> Path:
    relative = Path(score.imported_relative_path)
    if relative.is_absolute():
        raise ValueError("Registered score source path must remain inside the project")
    stored = (project / relative).resolve()
    if not stored.is_relative_to(project):
        raise ValueError("Registered score source path must remain inside the project")
    if not stored.is_file() or sha256_file(stored) != score.source_sha256:
        raise IOError("Registered score source bytes do not match the project score contract")
    return stored


def _require_score_rights_review(project: Path, score: ProjectScoreSource) -> None:
    inventory = build_project_source_inventory(project)
    matching = [
        item
        for item in inventory.local_sources
        if item.route_action == "register_score_source"
        and item.source_sha256.lower() == score.source_sha256.lower()
    ]
    if not matching:
        raise ValueError("Registered score has no matching source-intake receipt")
    if all(item.human_rights_review_required for item in matching):
        raise ValueError(
            "Registered score rights/provenance still require human review; run cdlc-source-rights first"
        )


def _selected_mappings(
    score: ProjectScoreSource,
    roles: Iterable[ArrangementRole] | None,
) -> list[ScoreArrangementMapping]:
    requested = list(roles) if roles is not None else None
    if requested is not None and len(set(requested)) != len(requested):
        raise ValueError("Each arrangement role may be requested at most once")

    if requested is None:
        mappings = [mapping for mapping in score.arrangement_mappings if mapping.human_confirmed]
        if not mappings:
            raise ValueError("No human-confirmed score mappings are available for fan-out")
        return sorted(mappings, key=lambda mapping: mapping.role.value)

    mappings: list[ScoreArrangementMapping] = []
    for role in requested:
        mapping = score.mapping_for(role)
        if mapping is None or not mapping.human_confirmed:
            raise ValueError(f"{role.value} score mapping is not human-confirmed")
        mappings.append(mapping)
    if not mappings:
        raise ValueError("At least one arrangement role is required for fan-out")
    return mappings


def _project_relative(project: Path, output: Path) -> str:
    resolved = output.resolve()
    if not resolved.is_relative_to(project):
        raise ValueError(f"Imported arrangement output escaped project directory: {resolved}")
    return resolved.relative_to(project).as_posix()


def _validate_output(
    output: Path,
    *,
    score: ProjectScoreSource,
    mapping: ScoreArrangementMapping,
) -> None:
    imported = ImportedSource.read_json(output)
    if imported.provenance.source_sha256 != score.source_sha256:
        raise ValueError("Fan-out output provenance does not match the registered score snapshot")
    if len(imported.tracks) != 1:
        raise ValueError("Fan-out output must contain exactly one normalized source track")
    track = imported.tracks[0]
    if track.source_track_index != mapping.source_track_index:
        raise ValueError("Fan-out output does not match the human-confirmed score track")
    if track.instrument != mapping.role.value:
        raise ValueError("Fan-out output does not match the human-confirmed arrangement role")


def _remove_stale_dlcbuilder_state(project: Path) -> None:
    staging = project / "build" / "dlcbuilder"
    if not staging.exists():
        return
    shutil.rmtree(staging)
    if staging.exists():
        raise OSError(
            "Stale DLC Builder staging could not be removed; refusing to publish new Bass fan-out authority"
        )


def _invalidate_stale_bass_derivatives(
    project: Path,
    *,
    score: ProjectScoreSource,
    mappings: list[ScoreArrangementMapping],
) -> None:
    bass_mapping = next((mapping for mapping in mappings if mapping.role is ArrangementRole.bass), None)
    if bass_mapping is None:
        return

    reconciliation_path = project / "charts" / "bass_reconciled.json"
    reconciliation_matches = False
    if reconciliation_path.is_file():
        try:
            reconciliation = ReconciledBassChart.model_validate_json(
                reconciliation_path.read_text(encoding="utf-8")
            )
            reconciliation_matches = (
                reconciliation.source_sha256 == score.source_sha256
                and reconciliation.track_index == bass_mapping.source_track_index
            )
        except (OSError, ValueError, ValidationError):
            reconciliation_matches = False

    disagreement_path = project / "review" / "source_disagreements.json"
    disagreement_matches = False
    if disagreement_path.is_file():
        try:
            disagreement = SourceDisagreementReport.model_validate_json(
                disagreement_path.read_text(encoding="utf-8")
            )
            disagreement_matches = (
                disagreement.source_sha256 == score.source_sha256
                and disagreement.track_index == bass_mapping.source_track_index
            )
        except (OSError, ValueError, ValidationError):
            disagreement_matches = False

    if not reconciliation_matches:
        reconciliation_path.unlink(missing_ok=True)
    if not (reconciliation_matches and disagreement_matches):
        disagreement_path.unlink(missing_ok=True)

    # Mapping, validation, authoring-export, and DLC Builder staging artifacts do not
    # currently carry enough source identity to prove they belong to the current Bass
    # reconciliation. Any Bass fan-out therefore invalidates them conservatively.
    for relative in (
        "charts/bass_mapped.json",
        "review/bass_mapping_review.json",
        "review/validation_report.json",
        "review/flags.json",
        "review/summary.md",
        "eof/arr_bass_RS2.xml",
        "eof/export_manifest.json",
        "eof/README.md",
    ):
        (project / relative).unlink(missing_ok=True)

    # DLC Builder projects may contain multiple arrangements, but any staged project
    # that includes Bass references the now-invalidated Bass XML. Removal is fail-closed:
    # if Windows or another process holds a staged file open, fan-out must abort rather
    # than publish a new authority marker beside stale package state.
    _remove_stale_dlcbuilder_state(project)


def fanout_confirmed_score_mappings(
    project_dir: Path,
    *,
    roles: Iterable[ArrangementRole] | None = None,
) -> ScoreFanoutResult:
    """Import human-confirmed Bass/Lead/Rhythm tracks from one registered score.

    This deterministic bridge consumes only explicit human mapping decisions and only
    after score rights/provenance are no longer review-pending. The registered immutable
    score copy is the sole input. Mapping confirmation and fan-out share one project
    transaction lock, so imports, validation, and manifest publication are serialized
    with remapping and with other fan-out runs.
    """

    project = _project(project_dir)
    with score_mapping_transaction(project):
        score = load_score_for_mapping_review(project)
        _require_score_rights_review(project, score)
        if score.source_format not in _SUPPORTED_FANOUT_FORMATS:
            raise ValueError(f"Score fan-out does not yet support {score.source_format}")

        stored_score = _reviewed_score_path(project, score)
        mappings = _selected_mappings(score, roles)
        manifest_path = (
            project / "sources" / "imported" / f"score-fanout-{score.source_sha256[:12]}.json"
        )
        # The manifest is the authority marker for a coherent fan-out snapshot. Remove
        # any previous marker before fallible imports can overwrite individual outputs.
        manifest_path.unlink(missing_ok=True)

        entries: list[ScoreFanoutEntry] = []
        outputs: dict[str, str] = {}
        for mapping in mappings:
            if score.source_format in {"gp3", "gp4", "gp5"}:
                output = import_project_guitarpro(
                    project,
                    stored_score,
                    track_index=mapping.source_track_index,
                    instrument=mapping.role.value,
                )
            else:
                output = import_project_musicxml(
                    project,
                    stored_score,
                    part_index=mapping.source_track_index,
                    instrument=mapping.role.value,
                )
            output = Path(output).resolve()
            _validate_output(output, score=score, mapping=mapping)
            relative_output = _project_relative(project, output)
            entries.append(
                ScoreFanoutEntry(
                    role=mapping.role,
                    source_track_index=mapping.source_track_index,
                    output_json=relative_output,
                )
            )
            outputs[mapping.role.value] = str(output)

        if sha256_file(stored_score) != score.source_sha256:
            raise IOError("Registered score bytes changed during arrangement fan-out")

        # A newly authoritative Bass score track supersedes Bass derivatives created
        # from another source/track. Provenance-bound reconciliation/review may survive
        # when they match; unbound downstream outputs never do.
        _invalidate_stale_bass_derivatives(project, score=score, mappings=mappings)

        manifest = ScoreFanoutManifest(
            score_source_sha256=score.source_sha256,
            score_source_format=score.source_format,
            arrangements=entries,
        )
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return ScoreFanoutResult(manifest_path=str(manifest_path), outputs=outputs)
