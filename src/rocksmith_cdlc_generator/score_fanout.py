from __future__ import annotations

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
from .source_import import ImportedSource, SourceTrack

if TYPE_CHECKING:
    # Deferred to a function-local import at runtime: score_role_composition_fanout_review
    # imports _require_score_rights_review/_reviewed_score_path from *this* module, so a
    # top-level import here would be a circular import.
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


def _current_composed_bass_record(
    project: Path, *, score: ProjectScoreSource
) -> "RoleCompositionFanoutRecord | None":
    """Return the currently valid composed multi-track record for Bass, if selected.

    Returns ``None`` when the persisted score role composition selects at most one track
    for Bass (nothing to compose) or when there is no persisted composition plan/selection
    at all -- in both cases the ordinary single-track fan-out path below is used unchanged.

    Fails closed (raises ``ValueError``) when Bass's composition selects more than one
    source track but no current composed fan-out record exists yet for that exact
    selection (``score_role_composition_fanout_review.
    compose_and_persist_score_role_composition_fanout`` has not been run, or a previously
    composed record is stale for the current composition plan/score/track content).
    Silently fanning out Bass from the primary track alone in that case would
    under-represent reviewed musical material the human explicitly composed, with no
    signal that it was dropped. This mirrors ``shared_guitar.py``'s
    ``_current_composed_record_for_role``, landed for Lead/Rhythm in the prior slice of
    issue #232.

    This is a best-effort check for the *plan*: it never validates or repairs the
    composition plan itself (``score_role_composition_workspace_status`` is authoritative
    for that). A missing, stale, or unreadable plan is silently treated as "nothing to
    guard against" here, since it is surfaced to the human elsewhere. Once a selection of
    more than one track exists, the persisted composed fan-out record *is* the guarded
    thing, so its own staleness is not swallowed the same way.

    Must be called from inside an already-held ``score_mapping_transaction`` lock (this
    project's underlying OS file lock is not re-entrant), which is why this loads the
    fan-out layer through the lock-assuming ``_load_current_locked`` rather than the
    public transaction-opening ``load_current_score_role_composition_fanout``.
    """

    plan_path = project / SCORE_ROLE_COMPOSITION_PATH
    if not plan_path.is_file():
        return None
    try:
        plan = ScoreRoleCompositionPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
        plan = validate_score_role_composition(score, plan)
    except (OSError, ValueError, ValidationError):
        return None
    selection = plan.selection_for(ArrangementRole.bass)
    if selection is None or len(selection.source_track_indices) <= 1:
        return None

    # Deferred import: see the TYPE_CHECKING note at the top of this module.
    from .score_role_composition_fanout_review import _load_current_locked as _load_current_fanout_locked

    layer = _load_current_fanout_locked(project)
    record = None if layer is None else layer.record_for(ArrangementRole.bass)
    if record is None:
        raise ValueError(
            f"bass has {len(selection.source_track_indices)} score tracks selected via score role "
            "composition "
            f"({', '.join(str(index) for index in selection.source_track_indices)}), but no current "
            "composed fan-out record exists for it yet; fan-out would otherwise fall back to only "
            "the primary track. Compose this role's multi-track selection (resolve any overlap "
            "findings, then run score role composition fan-out) before fanning out this "
            "arrangement."
        )
    return record


def _composition_output_file(project: Path, relative: str) -> Path:
    resolved = (project / relative).resolve()
    if not resolved.is_relative_to(project) or not resolved.is_file():
        raise ValueError(f"composition fan-out output is missing or escaped the project directory: {relative}")
    return resolved


def _single_bass_composition_track(source: ImportedSource, *, track_index: int) -> SourceTrack:
    matches = [track for track in source.tracks if track.source_track_index == track_index]
    if len(matches) != 1:
        raise ValueError(f"bass composition track output does not contain exactly one track {track_index}")
    return matches[0]


def _materialize_composed_bass_source(
    project: Path, *, record: "RoleCompositionFanoutRecord"
) -> Path:
    """Merge every contributing composed Bass track output into one single-track source.

    Every downstream Bass consumer (``reconcile_bass_sources``/``reconcile_project_bass``,
    and everything built on ``ReconciledBassChart``) reads exactly one ``ImportedSource``
    containing exactly one ``SourceTrack``, matched by ``source_track_index``. This
    materializes the already human-composed multi-track note stream (``record.notes``,
    already start-time ordered by ``compose_role_notes``) as that single-track shape,
    tagged with Bass's confirmed *primary* track index (``record.source_track_indices[0]``,
    which ``validate_score_role_composition`` already guarantees equals the confirmed
    mapping's ``source_track_index``), so every one of those consumers accepts it
    unchanged. Mirrors ``shared_guitar.py``'s ``_materialize_composed_guitar_source``,
    landed for Lead/Rhythm in the prior slice of issue #232.

    Score-level fields shared by the contributing tracks (tempo, time signatures, beat
    grid, tuning) are taken from the persisted per-track imports and cross-checked for
    exact agreement first; this never silently picks one contributing track's values over
    another's on the assumption that they must match because it is "the same score file".
    """

    if not record.track_outputs:
        raise ValueError("bass composition fan-out has no track outputs to merge")

    track_sources = [
        (
            track_output.source_track_index,
            ImportedSource.read_json(_composition_output_file(project, track_output.output_json)),
        )
        for track_output in record.track_outputs
    ]
    primary_index, primary_source = track_sources[0]
    primary_track = _single_bass_composition_track(primary_source, track_index=primary_index)

    for track_index, source in track_sources[1:]:
        track = _single_bass_composition_track(source, track_index=track_index)
        if source.ticks_per_beat != primary_source.ticks_per_beat:
            raise ValueError("bass composition tracks disagree on ticks_per_beat")
        if source.tempo_events != primary_source.tempo_events:
            raise ValueError("bass composition tracks disagree on tempo_events")
        if source.time_signatures != primary_source.time_signatures:
            raise ValueError("bass composition tracks disagree on time_signatures")
        if source.beat_times_seconds != primary_source.beat_times_seconds:
            raise ValueError("bass composition tracks disagree on beat_times_seconds")
        if track.tuning_midi != primary_track.tuning_midi:
            raise ValueError("bass composition tracks disagree on tuning_midi")

    merged_warnings: list[str] = []
    for _, source in track_sources:
        merged_warnings.extend(source.warnings)

    merged_track = SourceTrack(
        source_track_index=primary_index,
        name=primary_track.name,
        instrument=ArrangementRole.bass.value,
        channel_numbers=primary_track.channel_numbers,
        program_numbers=primary_track.program_numbers,
        tuning_midi=primary_track.tuning_midi,
        notes=[
            item.note.model_copy(
                update={
                    "composition_source_track_index": item.source_track_index,
                    "composition_source_event_index": item.event_index,
                }
            )
            for item in record.notes
        ],
    )
    merged = ImportedSource(
        provenance=primary_source.provenance,
        ticks_per_beat=primary_source.ticks_per_beat,
        tempo_events=primary_source.tempo_events,
        time_signatures=primary_source.time_signatures,
        beat_times_seconds=primary_source.beat_times_seconds,
        tracks=[merged_track],
        warnings=merged_warnings,
    )
    path = (
        project
        / "sources"
        / "imported"
        / "composition"
        / f"bass-composed-{record.score_sha256[:12]}.json"
    )
    merged.write_json(path)
    return path


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


def _invalidate_stale_bass_derivatives(
    project: Path,
    *,
    score: ProjectScoreSource,
    mappings: list[ScoreArrangementMapping],
    bass_output_content_sha256: str | None = None,
) -> None:
    """Purge Bass derivatives that no longer match the score/track/content just fanned out.

    ``(score_sha256, track_index)`` alone is not enough: a human-composed multi-track
    Bass selection (issue #232) can change the actual note content fanned out for the
    same confirmed *primary* track index (e.g. adding a second contributing track), which
    would otherwise leave a reconciliation built from the old, narrower note stream
    looking "current". ``bass_output_content_sha256`` -- the content hash of the exact
    Bass fan-out output this call just produced (or is about to produce) -- closes that
    gap by also requiring the persisted reconciliation's own recorded
    ``source_content_sha256`` to match. A ``None`` on either side never counts as a match:
    an older reconciliation predating that field, or a caller that cannot supply the new
    output's hash, is treated conservatively as unproven rather than silently trusted.
    """

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
                and reconciliation.source_content_sha256 is not None
                and reconciliation.source_content_sha256 == bass_output_content_sha256
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
                and disagreement.source_content_sha256 is not None
                and disagreement.source_content_sha256 == bass_output_content_sha256
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
            composed_bass_record = None
            if mapping.role is ArrangementRole.bass:
                composed_bass_record = _current_composed_bass_record(project, score=score)
            if composed_bass_record is not None:
                output = _materialize_composed_bass_source(project, record=composed_bass_record)
            elif score.source_format in {"gp3", "gp4", "gp5"}:
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

        # A newly authoritative Bass score track (or composed multi-track note stream)
        # supersedes Bass derivatives created from another source/track/content.
        # Provenance-bound reconciliation/review may survive when they match; unbound
        # downstream outputs never do.
        bass_output = outputs.get(ArrangementRole.bass.value)
        _invalidate_stale_bass_derivatives(
            project,
            score=score,
            mappings=mappings,
            bass_output_content_sha256=sha256_file(Path(bass_output)) if bass_output is not None else None,
        )

        manifest = ScoreFanoutManifest(
            score_source_sha256=score.source_sha256,
            score_source_format=score.source_format,
            arrangements=entries,
        )
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return ScoreFanoutResult(manifest_path=str(manifest_path), outputs=outputs)
