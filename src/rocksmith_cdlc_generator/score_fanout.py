from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .guitarpro_import import import_project_guitarpro
from .hashing import sha256_file
from .musicxml_import import import_project_musicxml
from .package_generation import invalidate_package_state
from .project_source_inventory import build_project_source_inventory
from .reconciliation import ReconciledBassChart, SourceDisagreementReport
from .score_mapping_review import load_score_for_mapping_review, score_mapping_transaction
from .score_role_composition import ScoreRoleCompositionPlan, validate_score_role_composition
from .score_role_composition_review import SCORE_ROLE_COMPOSITION_PATH
from .score_source import ArrangementRole, ProjectScoreSource, ScoreArrangementMapping
from .source_import import ImportedSource

if TYPE_CHECKING:
    # Deferred at runtime (imported inside ``_current_bass_composed_identity``):
    # score_role_composition_fanout_review.py imports from this module at its own top
    # level, so a module-level import here would be circular.
    from .score_role_composition_fanout_review import RoleCompositionFanoutRecord

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


def _reject_unconsumed_multi_track_bass_composition(project: Path, *, score: ProjectScoreSource) -> None:
    """Fail closed rather than silently fanning out only Bass's primary confirmed track.

    Bass's fan-out path (this module) imports exactly one score track per role through
    each role's single human-confirmed ``source_track_index`` mapping. If a human has
    selected more than one source track for Bass via score role composition
    (``cdlc-score-composition``/the Song Workspace composition panel), silently fanning
    out the primary track alone would under-represent reviewed musical material the human
    explicitly composed, with no signal that it was dropped. Composed multi-track
    note-stream consumption is not yet wired into Bass's fan-out/reconciliation pipeline
    (tracked as the remaining part of issue #232, mirroring the equivalent guard already
    added for Lead/Rhythm in ``shared_guitar.py``'s
    ``_reject_unconsumed_multi_track_composition``), so fail closed instead.

    Same best-effort scope as the Lead/Rhythm guard: a missing, stale, or unreadable
    composition plan is silently treated as "nothing to guard against" here, since
    ``score_role_composition_workspace_status`` remains authoritative for surfacing that
    to the human elsewhere.
    """

    plan_path = project / SCORE_ROLE_COMPOSITION_PATH
    if not plan_path.is_file():
        return
    try:
        plan = ScoreRoleCompositionPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
        plan = validate_score_role_composition(score, plan)
    except (OSError, ValueError, ValidationError):
        return
    selection = plan.selection_for(ArrangementRole.bass)
    if selection is None or len(selection.source_track_indices) <= 1:
        return
    raise ValueError(
        f"bass has {len(selection.source_track_indices)} score tracks selected via score role "
        "composition "
        f"({', '.join(str(index) for index in selection.source_track_indices)}), but Bass fan-out "
        "does not yet consume composed multi-track output; it would otherwise fan out silently "
        "from only the primary track. Compose and consume the multi-track selection once "
        "supported, or reduce the composition selection back to a single track, before fanning "
        "out this arrangement."
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
    # Bass fan-out changes package inputs. Advance package authority first, then remove
    # DLC Builder and returned/staged PSARC state together.
    invalidate_package_state(project)


def _record_content_sha256(record: RoleCompositionFanoutRecord) -> str:
    return hashlib.sha256(record.model_dump_json().encode("utf-8")).hexdigest()


def _current_bass_composed_identity(
    project: Path, *, score: ProjectScoreSource
) -> tuple[list[int] | None, str | None]:
    """Return the current fan-out content identity Bass derivatives must be bound to.

    Closes "Trap 2" from docs/score-role-composition-fanout-review.md: staleness keyed
    on ``(score_sha256, track_index)`` alone cannot see a score role composition
    selection change (adding, removing, or reordering a second/third source track) that
    leaves the confirmed *primary* ``source_track_index`` unchanged, so a reconciliation
    built from an older/smaller composed note stream would be wrongly treated as still
    current. This mirrors ``shared_guitar.py``'s ``composed_source_track_indices`` /
    ``composed_fanout_record_sha256`` binding for Lead/Rhythm.

    Returns ``(None, None)`` -- the ordinary single-track identity, matching every
    ``ReconciledBassChart``/``SourceDisagreementReport`` produced by the current
    (single-track only) ``reconcile_bass_sources`` -- whenever the persisted score role
    composition plan is missing, stale, unreadable, or selects at most one source track
    for Bass. When the plan selects more than one track, returns the selected, ordered
    ``source_track_indices`` together with the current composed fan-out record's content
    hash when a valid current record exists for that exact selection, or a ``None`` hash
    when it does not (selection changed but not yet recomposed). Either way this never
    equals a derivative's default ``(None, None)`` identity, so a derivative built before
    the composition selected more than one track -- or built for a different composed
    track set/content -- is correctly detected as stale rather than silently kept.

    Same best-effort scope as ``_reject_unconsumed_multi_track_bass_composition``: a
    missing, stale, or unreadable composition plan is silently treated as "nothing
    composed" here, since ``score_role_composition_workspace_status`` remains
    authoritative for surfacing that to the human elsewhere.
    """

    plan_path = project / SCORE_ROLE_COMPOSITION_PATH
    if not plan_path.is_file():
        return None, None
    try:
        plan = ScoreRoleCompositionPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
        plan = validate_score_role_composition(score, plan)
    except (OSError, ValueError, ValidationError):
        return None, None
    selection = plan.selection_for(ArrangementRole.bass)
    if selection is None or len(selection.source_track_indices) <= 1:
        return None, None

    from .score_role_composition_fanout_review import _load_current_locked

    try:
        layer = _load_current_locked(project)
    except (OSError, ValueError, ValidationError):
        layer = None
    record = None if layer is None else layer.record_for(ArrangementRole.bass)
    record_sha256 = None if record is None else _record_content_sha256(record)
    return list(selection.source_track_indices), record_sha256


def _invalidate_stale_bass_derivatives(
    project: Path,
    *,
    score: ProjectScoreSource,
    mappings: list[ScoreArrangementMapping],
) -> None:
    bass_mapping = next((mapping for mapping in mappings if mapping.role is ArrangementRole.bass), None)
    if bass_mapping is None:
        return

    composed_indices, composed_record_sha256 = _current_bass_composed_identity(project, score=score)

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
                and reconciliation.composed_source_track_indices == composed_indices
                and reconciliation.composed_fanout_record_sha256 == composed_record_sha256
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
                and disagreement.composed_source_track_indices == composed_indices
                and disagreement.composed_fanout_record_sha256 == composed_record_sha256
            )
        except (OSError, ValueError, ValidationError):
            disagreement_matches = False

    if not reconciliation_matches:
        reconciliation_path.unlink(missing_ok=True)
    if not (reconciliation_matches and disagreement_matches):
        disagreement_path.unlink(missing_ok=True)

    # Mapping, validation, authoring-export, and package staging artifacts do not
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
            if mapping.role is ArrangementRole.bass:
                _reject_unconsumed_multi_track_bass_composition(project, score=score)
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
