from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .guitarpro_import import import_guitarpro
from .hashing import sha256_file
from .musicxml_import import import_musicxml
from .score_fanout import _require_score_rights_review, _reviewed_score_path
from .score_mapping_review import load_score_for_mapping_review, score_mapping_transaction
from .score_role_composition import ScoreRoleCompositionPlan, validate_score_role_composition
from .score_role_composition_fanout import (
    ComposedSourceNote,
    _role_scoped_overlap_report,
    compose_role_notes,
)
from .score_role_composition_overlap import ScoreRoleCompositionOverlapReport
from .score_role_composition_overlap_review import ScoreRoleCompositionOverlapDecisionPlan
from .score_role_composition_review import SCORE_ROLE_COMPOSITION_PATH
from .score_source import ArrangementRole, ProjectScoreSource
from .source_import import SourceTrack

SCORE_ROLE_COMPOSITION_FANOUT_PATH = Path("review") / "score_role_composition_fanout.json"
_SUPPORTED_FANOUT_FORMATS = {"gp3", "gp4", "gp5", "musicxml", "mxl"}
_ROLE_ORDER = {"lead": 0, "rhythm": 1, "bass": 2}


class ComposedTrackOutput(BaseModel):
    """Provenance-bound project-local import of one exact composition source track."""

    model_config = ConfigDict(frozen=True)

    source_track_index: int = Field(ge=0)
    output_json: str
    output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RoleCompositionFanoutRecord(BaseModel):
    """Persisted composed note stream for one role, bound to its full source-track set.

    Unlike a single-track fan-out entry, staleness is bound to the exact ordered list of
    every selected source track, not to one track identity. Any drift in the persisted
    composition plan's track set, or in any one imported track's bytes, invalidates the
    whole record rather than silently keeping a partially current result.
    """

    model_config = ConfigDict(frozen=True)

    role: ArrangementRole
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_format: str
    source_track_indices: list[int]
    track_outputs: list[ComposedTrackOutput]
    notes: list[ComposedSourceNote] = Field(default_factory=list)

    @model_validator(mode="after")
    def track_outputs_match_source_set(self) -> "RoleCompositionFanoutRecord":
        output_indices = [item.source_track_index for item in self.track_outputs]
        if output_indices != list(self.source_track_indices):
            raise ValueError(
                "composition fan-out track outputs must match the full selected track set, in order"
            )
        return self


class ScoreRoleCompositionFanoutReviewLayer(BaseModel):
    """Provenance-bearing composed fan-out bound to one exact current score/plan."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_format: str
    records: list[RoleCompositionFanoutRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_roles(self) -> "ScoreRoleCompositionFanoutReviewLayer":
        roles = [record.role for record in self.records]
        if len(roles) != len(set(roles)):
            raise ValueError("composition fan-out review contains duplicate role records")
        return self

    def record_for(self, role: ArrangementRole) -> RoleCompositionFanoutRecord | None:
        return next((item for item in self.records if item.role is role), None)


def _project(project_dir: Path) -> Path:
    project = project_dir.expanduser().resolve()
    if not (project / "project.json").is_file():
        raise FileNotFoundError(f"Not a CDLC project: {project}")
    return project


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _current_composition_plan_locked(
    project: Path,
    score: ProjectScoreSource,
) -> ScoreRoleCompositionPlan | None:
    # Reimplemented rather than calling score_role_composition_review's transaction-
    # wrapped loader: this helper always runs from inside an already-held score mapping
    # transaction lock, and the underlying OS file lock is not re-entrant.
    path = project / SCORE_ROLE_COMPOSITION_PATH
    if not path.is_file():
        return None
    plan = ScoreRoleCompositionPlan.model_validate_json(path.read_text(encoding="utf-8"))
    return validate_score_role_composition(score, plan)


def _track_output_path(
    project: Path,
    *,
    role: ArrangementRole,
    track_index: int,
    score: ProjectScoreSource,
) -> Path:
    return (
        project
        / "sources"
        / "imported"
        / "composition"
        / f"{role.value}-track{track_index}-{score.source_sha256[:12]}.json"
    )


def _import_selected_track(
    score: ProjectScoreSource,
    stored_score: Path,
    *,
    track_index: int,
    role: ArrangementRole,
):
    if score.source_format in {"gp3", "gp4", "gp5"}:
        imported = import_guitarpro(stored_score, track_index=track_index, instrument=role.value)
    elif score.source_format in {"musicxml", "mxl"}:
        imported = import_musicxml(stored_score, part_index=track_index, instrument=role.value)
    else:  # pragma: no cover - guarded by _SUPPORTED_FANOUT_FORMATS before this is reached
        raise ValueError(f"Score role composition fan-out does not yet support {score.source_format}")

    if imported.provenance.source_sha256 != score.source_sha256:
        raise IOError("Registered score bytes changed during composition fan-out")
    if len(imported.tracks) != 1:
        raise ValueError("Composition fan-out import must contain exactly one source track")
    track = imported.tracks[0]
    if track.source_track_index != track_index:
        raise ValueError("Composition fan-out import does not match the requested source track")
    if track.instrument != role.value:
        raise ValueError("Composition fan-out import does not match the requested arrangement role")
    return imported


def _validate_record_locked(
    project: Path,
    score: ProjectScoreSource,
    plan: ScoreRoleCompositionPlan | None,
    record: RoleCompositionFanoutRecord,
) -> None:
    if record.score_sha256 != score.source_sha256 or record.score_format != score.source_format:
        raise ValueError(f"{record.role.value} composition fan-out is stale for the registered score")

    selection = plan.selection_for(record.role) if plan is not None else None
    if selection is None or selection.source_track_indices != record.source_track_indices:
        raise ValueError(
            f"{record.role.value} composition fan-out is stale for the current composition track set"
        )

    for track_output in record.track_outputs:
        output = (project / track_output.output_json).resolve()
        if not output.is_relative_to(project) or not output.is_file():
            raise ValueError(f"{record.role.value} composition fan-out output is missing")
        if sha256_file(output) != track_output.output_sha256:
            raise ValueError(
                f"{record.role.value} composition fan-out is stale for current track output content"
            )


def _load_current_locked(project: Path) -> ScoreRoleCompositionFanoutReviewLayer | None:
    path = project / SCORE_ROLE_COMPOSITION_FANOUT_PATH
    if not path.is_file():
        return None
    score = load_score_for_mapping_review(project)
    plan = _current_composition_plan_locked(project, score)
    layer = ScoreRoleCompositionFanoutReviewLayer.model_validate_json(path.read_text(encoding="utf-8"))
    if layer.score_sha256 != score.source_sha256 or layer.score_format != score.source_format:
        raise ValueError("Score role composition fan-out review is stale for the registered score")
    for record in layer.records:
        _validate_record_locked(project, score, plan, record)
    return layer


def load_current_score_role_composition_fanout(
    project_dir: Path,
) -> ScoreRoleCompositionFanoutReviewLayer | None:
    """Load the persisted composed fan-out, failing closed on any provenance/content drift."""

    project = _project(project_dir)
    with score_mapping_transaction(project):
        return _load_current_locked(project)


def preview_score_role_composition_overlaps(
    project_dir: Path,
    *,
    role: ArrangementRole,
) -> ScoreRoleCompositionOverlapReport:
    """Import the currently selected source tracks for one role and report overlaps.

    This performs the same score/rights/plan/track-import steps as
    ``compose_and_persist_score_role_composition_fanout`` but is read-only: it never
    writes track outputs, a composed note stream, or the persisted fan-out record. It
    exists so a human (via CLI or Song Workspace) can inspect the exact cross-track
    overlap evidence for the currently selected tracks before recording explicit
    per-overlap decisions and composing. Fails closed under the same conditions as
    composing: unreviewed rights, an unsupported score format, a missing persisted
    composition plan, or a role with no current selection.
    """

    project = _project(project_dir)
    with score_mapping_transaction(project):
        score = load_score_for_mapping_review(project)
        _require_score_rights_review(project, score)
        if score.source_format not in _SUPPORTED_FANOUT_FORMATS:
            raise ValueError(f"Score role composition fan-out does not yet support {score.source_format}")
        stored_score = _reviewed_score_path(project, score)

        plan = _current_composition_plan_locked(project, score)
        if plan is None:
            raise ValueError("No persisted score role composition plan is available")
        selection = plan.selection_for(role)
        if selection is None:
            raise ValueError(f"{role.value} has no current composition selection")

        tracks = [
            _import_selected_track(score, stored_score, track_index=track_index, role=role).tracks[0]
            for track_index in selection.source_track_indices
        ]

        return _role_scoped_overlap_report(plan, tracks, role=role)


def compose_and_persist_score_role_composition_fanout(
    project_dir: Path,
    *,
    role: ArrangementRole,
    decisions: ScoreRoleCompositionOverlapDecisionPlan,
) -> RoleCompositionFanoutRecord:
    """Import every currently selected source track and persist one composed note stream.

    This imports (or re-imports) every source track currently selected for ``role`` in
    the persisted composition plan, merges them per the supplied human overlap decisions
    using ``compose_role_notes``, and atomically persists the result. Staleness is bound
    to the full ordered selected track set, not to one track identity: a later plan
    change, decision gap, or track content drift makes the persisted record fail closed
    on the next read rather than silently remaining authoritative.

    This does not accept/change source rights, primary mapping confirmation, timing,
    fingering, technique, chord, or tone decisions, and does not write Rocksmith XML,
    package CDLC, modify the live Rocksmith installation, or interact with
    NoCableLauncher.
    """

    project = _project(project_dir)
    with score_mapping_transaction(project):
        score = load_score_for_mapping_review(project)
        _require_score_rights_review(project, score)
        if score.source_format not in _SUPPORTED_FANOUT_FORMATS:
            raise ValueError(f"Score role composition fan-out does not yet support {score.source_format}")
        stored_score = _reviewed_score_path(project, score)

        plan = _current_composition_plan_locked(project, score)
        if plan is None:
            raise ValueError("No persisted score role composition plan is available")
        selection = plan.selection_for(role)
        if selection is None:
            raise ValueError(f"{role.value} has no current composition selection")

        track_outputs: list[ComposedTrackOutput] = []
        tracks: list[SourceTrack] = []
        for track_index in selection.source_track_indices:
            imported = _import_selected_track(score, stored_score, track_index=track_index, role=role)
            output_path = _track_output_path(project, role=role, track_index=track_index, score=score)
            imported.write_json(output_path)
            track_outputs.append(
                ComposedTrackOutput(
                    source_track_index=track_index,
                    output_json=output_path.relative_to(project).as_posix(),
                    output_sha256=sha256_file(output_path),
                )
            )
            tracks.append(imported.tracks[0])

        if sha256_file(stored_score) != score.source_sha256:
            raise IOError("Registered score bytes changed during composition fan-out")

        result = compose_role_notes(plan, decisions, tracks, role=role)

        record = RoleCompositionFanoutRecord(
            role=role,
            score_sha256=result.score_sha256,
            score_format=result.score_format,
            source_track_indices=result.source_track_indices,
            track_outputs=track_outputs,
            notes=result.notes,
        )

        try:
            current = _load_current_locked(project)
        except ValueError:
            # Stale/corrupt prior review cannot grant authority to the current
            # composition. The freshly composed record below is fully revalidated
            # against current score/plan/track content, so replace the stale layer
            # wholesale rather than requiring a manual file deletion first.
            current = None
        records = [] if current is None else list(current.records)
        records = [item for item in records if item.role is not role]
        records.append(record)
        records.sort(key=lambda item: _ROLE_ORDER[item.role.value])

        layer = ScoreRoleCompositionFanoutReviewLayer(
            score_sha256=score.source_sha256,
            score_format=score.source_format,
            records=records,
        )
        _atomic_write(
            project / SCORE_ROLE_COMPOSITION_FANOUT_PATH,
            layer.model_dump_json(indent=2) + "\n",
        )
        return record
