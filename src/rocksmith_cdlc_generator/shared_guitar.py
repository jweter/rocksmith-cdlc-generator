from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .guitar_authoring import GuitarAuthoringChart, build_guitar_authoring_chart
from .hashing import sha256_file
from .package_generation import bump_package_generation
from .reviewed_chords import current_reviewed_chords_sha256, reviewed_chord_groups
from .reviewed_event_timing import (
    apply_reviewed_event_timing_to_source,
    current_reviewed_event_timing_sha256,
)
from .reviewed_positions import apply_reviewed_positions, current_reviewed_positions_sha256
from .reviewed_techniques import (
    apply_reviewed_techniques_to_source,
    current_reviewed_techniques_sha256,
)
from .score_mapping_review import load_score_for_mapping_review, score_mapping_transaction
from .score_role_composition import ScoreRoleCompositionPlan, validate_score_role_composition
from .score_role_composition_fanout_review import (
    RoleCompositionFanoutRecord,
    load_current_score_role_composition_fanout,
)
from .score_role_composition_fanout_review import _load_current_locked as _load_current_fanout_locked
from .score_role_composition_review import SCORE_ROLE_COMPOSITION_PATH
from .score_source import ArrangementRole
from .shared_timeline import alignment_for_role, load_current_shared_timeline
from .source_import import ImportedSource, SourceTrack

SharedGuitarRole = Literal["lead", "rhythm"]


class SharedGuitarDraftManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    arrangement: SharedGuitarRole
    recording_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    shared_timeline_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_path: str
    source_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_track_index: int = Field(ge=0)
    position_review_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    event_timing_review_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    technique_review_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    chord_review_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    chart_path: str
    chart_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    # Present only when this draft was built by materializing a human-composed
    # multi-track note stream (score role composition, issue #232) rather than the
    # ordinary single confirmed-primary-track fan-out output. Both fields are bound
    # together: either both are set (composed) or both are None (single-track).
    composed_source_track_indices: list[int] | None = None
    composed_fanout_record_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path

    @classmethod
    def read_json(cls, path: Path) -> "SharedGuitarDraftManifest":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


def _role(arrangement: SharedGuitarRole) -> ArrangementRole:
    return ArrangementRole.lead if arrangement == "lead" else ArrangementRole.rhythm


def _safe_project_file(project: Path, path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_relative_to(project):
        raise ValueError("shared guitar source escaped the project directory")
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return resolved


def _shared_timeline_path(project: Path) -> Path:
    path = project / "analysis" / "shared_timeline.json"
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _invalidate_guitar_derivatives(project: Path, arrangement: SharedGuitarRole) -> None:
    # Publish a new package generation before stale package files are removed. A
    # concurrent register-psarc operation bound to the old generation then fails closed.
    bump_package_generation(project)
    for relative in (
        f"review/{arrangement}_validation_report.json",
        f"review/{arrangement}_flags.json",
        f"review/{arrangement}_summary.md",
        f"eof/arr_{arrangement}_RS2.xml",
        f"eof/{arrangement}_export_manifest.json",
        f"eof/{arrangement.upper()}_README.md",
    ):
        (project / relative).unlink(missing_ok=True)
    for stale_dir in (project / "build" / "dlcbuilder", project / "build" / "staging"):
        if stale_dir.exists():
            shutil.rmtree(stale_dir)
        if stale_dir.exists():
            raise OSError(f"Failed to invalidate stale package staging: {stale_dir}")


def _record_content_sha256(record: RoleCompositionFanoutRecord) -> str:
    return hashlib.sha256(record.model_dump_json().encode("utf-8")).hexdigest()


def _current_composed_record_for_role(
    project: Path, *, role: ArrangementRole
) -> RoleCompositionFanoutRecord | None:
    """Return the currently valid composed multi-track record for one role, if selected.

    Returns ``None`` when the role's persisted score role composition selects at most one
    track (nothing to compose) or when there is no persisted composition plan/selection at
    all -- in both cases the ordinary single-track fan-out path is used unchanged.

    Fails closed (raises ``ValueError``) when the role's composition selects more than one
    source track but no current composed fan-out record exists yet for that exact selection
    (``score_role_composition_fanout_review.compose_and_persist_score_role_composition_fanout``
    has not been run, or a previously composed record is stale for the current composition
    plan/score/track content). Silently building the arrangement draft from the primary
    track alone in that case would under-represent reviewed musical material the human
    explicitly composed, with no signal that it was dropped.

    This is a best-effort check for the *plan*: it never validates or repairs the
    composition plan itself (``score_role_composition_workspace_status`` is authoritative
    for that). A missing, stale, or unreadable plan is silently treated as "nothing to
    guard against" here, since it is surfaced to the human elsewhere. Once a selection of
    more than one track exists, the persisted composed fan-out record *is* the guarded
    thing, so its own staleness is not swallowed the same way.

    Must be called from inside an already-held ``score_mapping_transaction`` lock (this
    project's underlying OS file lock is not re-entrant), which is why this loads the
    fan-out layer through the lock-assuming ``_load_current_fanout_locked`` rather than the
    public transaction-opening ``load_current_score_role_composition_fanout``.
    """

    plan_path = project / SCORE_ROLE_COMPOSITION_PATH
    if not plan_path.is_file():
        return None
    try:
        score = load_score_for_mapping_review(project)
        plan = ScoreRoleCompositionPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
        plan = validate_score_role_composition(score, plan)
    except (OSError, ValueError, ValidationError):
        return None
    selection = plan.selection_for(role)
    if selection is None or len(selection.source_track_indices) <= 1:
        return None

    layer = _load_current_fanout_locked(project)
    record = None if layer is None else layer.record_for(role)
    if record is None:
        raise ValueError(
            f"{role.value} has {len(selection.source_track_indices)} score tracks selected via "
            "score role composition "
            f"({', '.join(str(index) for index in selection.source_track_indices)}), but no current "
            "composed fan-out record exists for it yet; building would otherwise fall back to only "
            "the primary track. Compose this role's multi-track selection (resolve any overlap "
            "findings, then run score role composition fan-out) before building this arrangement."
        )
    return record


def _single_track(source: ImportedSource, *, track_index: int, role: ArrangementRole) -> SourceTrack:
    matches = [track for track in source.tracks if track.source_track_index == track_index]
    if len(matches) != 1:
        raise ValueError(
            f"{role.value} composition track output does not contain exactly one track {track_index}"
        )
    return matches[0]


def _composed_guitar_source_path(
    project: Path, *, role: ArrangementRole, record: RoleCompositionFanoutRecord
) -> Path:
    return (
        project / "sources" / "imported" / "composition" / f"{role.value}-composed-{record.score_sha256[:12]}.json"
    )


def _materialize_composed_guitar_source(
    project: Path, *, role: ArrangementRole, record: RoleCompositionFanoutRecord
) -> Path:
    """Merge every contributing track output into one ordinary single-track ImportedSource.

    Every existing downstream consumer of a shared-guitar source (reviewed positions,
    reviewed event timing, reviewed techniques, reviewed chords, guitar authoring chart
    building) reads exactly one ``ImportedSource`` containing exactly one ``SourceTrack``,
    matched by ``source_track_index``. This materializes the already human-composed
    multi-track note stream (``record.notes``, already start-time ordered by
    ``compose_role_notes``) as that single-track shape, tagged with the role's confirmed
    *primary* track index (``record.source_track_indices[0]``, which
    ``validate_score_role_composition`` already guarantees equals the confirmed mapping's
    ``source_track_index``), so every one of those consumers accepts it unchanged.

    Score-level fields shared by the contributing tracks (tempo, time signatures, beat
    grid, tuning) are taken from the persisted per-track imports and cross-checked for
    exact agreement first; this never silently picks one contributing track's values over
    another's on the assumption that they must match because it is "the same score file".
    """

    if not record.track_outputs:
        raise ValueError(f"{role.value} composition fan-out has no track outputs to merge")

    track_sources = [
        (
            track_output.source_track_index,
            ImportedSource.read_json(_safe_project_file(project, project / track_output.output_json)),
        )
        for track_output in record.track_outputs
    ]
    primary_index, primary_source = track_sources[0]
    primary_track = _single_track(primary_source, track_index=primary_index, role=role)

    for track_index, source in track_sources[1:]:
        track = _single_track(source, track_index=track_index, role=role)
        if source.ticks_per_beat != primary_source.ticks_per_beat:
            raise ValueError(f"{role.value} composition tracks disagree on ticks_per_beat")
        if source.tempo_events != primary_source.tempo_events:
            raise ValueError(f"{role.value} composition tracks disagree on tempo_events")
        if source.time_signatures != primary_source.time_signatures:
            raise ValueError(f"{role.value} composition tracks disagree on time_signatures")
        if source.beat_times_seconds != primary_source.beat_times_seconds:
            raise ValueError(f"{role.value} composition tracks disagree on beat_times_seconds")
        if track.tuning_midi != primary_track.tuning_midi:
            raise ValueError(f"{role.value} composition tracks disagree on tuning_midi")

    merged_warnings: list[str] = []
    for _, source in track_sources:
        merged_warnings.extend(source.warnings)

    merged_track = SourceTrack(
        source_track_index=primary_index,
        name=primary_track.name,
        instrument=role.value,
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
    path = _composed_guitar_source_path(project, role=role, record=record)
    merged.write_json(path)
    return path


def _build_project_shared_guitar_chart_locked(
    project: Path,
    *,
    arrangement: SharedGuitarRole,
) -> Path:
    timeline = load_current_shared_timeline(project)
    timeline_path = _shared_timeline_path(project)
    role = _role(arrangement)
    composed_record = _current_composed_record_for_role(project, role=role)
    alignment = alignment_for_role(project, role)
    if composed_record is None:
        source_path = _safe_project_file(project, Path(alignment.source_path))
    else:
        source_path = _materialize_composed_guitar_source(project, role=role, record=composed_record)
    source = ImportedSource.read_json(source_path)
    reviewed_source, _applied_positions = apply_reviewed_positions(
        project,
        source,
        arrangement=arrangement,
        source_track_index=alignment.track_index,
    )
    reviewed_source, _applied_timing = apply_reviewed_event_timing_to_source(
        project,
        reviewed_source,
        arrangement=arrangement,
        source_track_index=alignment.track_index,
    )
    reviewed_source, _applied_techniques = apply_reviewed_techniques_to_source(
        project,
        reviewed_source,
        arrangement=arrangement,
        source_track_index=alignment.track_index,
    )
    explicit_chords = reviewed_chord_groups(
        project,
        arrangement=arrangement,
        source_track_index=alignment.track_index,
    )
    chart = build_guitar_authoring_chart(
        reviewed_source,
        alignment,
        arrangement=arrangement,
        track_index=alignment.track_index,
        reviewed_chord_groups=explicit_chords,
    )
    _invalidate_guitar_derivatives(project, arrangement)
    chart_path = project / "charts" / f"{arrangement}_source.json"
    chart.write_json(chart_path)
    manifest = SharedGuitarDraftManifest(
        arrangement=arrangement,
        recording_sha256=timeline.recording_sha256,
        score_sha256=timeline.score_sha256,
        shared_timeline_sha256=sha256_file(timeline_path),
        source_path=source_path.relative_to(project).as_posix(),
        source_content_sha256=sha256_file(source_path),
        source_track_index=alignment.track_index,
        position_review_sha256=current_reviewed_positions_sha256(project),
        event_timing_review_sha256=current_reviewed_event_timing_sha256(project),
        technique_review_sha256=current_reviewed_techniques_sha256(project),
        chord_review_sha256=current_reviewed_chords_sha256(project),
        chart_path=chart_path.relative_to(project).as_posix(),
        chart_sha256=sha256_file(chart_path),
        composed_source_track_indices=(
            None if composed_record is None else list(composed_record.source_track_indices)
        ),
        composed_fanout_record_sha256=(
            None if composed_record is None else _record_content_sha256(composed_record)
        ),
    )
    manifest.write_json(project / "charts" / f"{arrangement}_shared_timeline.json")
    return chart_path


def build_project_shared_guitar_chart(project_dir: Path, *, arrangement: SharedGuitarRole) -> Path:
    """Build Lead/Rhythm from one score/timeline authority transaction.

    Shared-timeline promotion, score remapping, and fan-out use the same project lock.
    Holding it across alignment materialization, chart generation, and manifest hashing
    prevents a newly promoted timeline from being paired with a chart built from the
    previous timing transform. A later promotion occurs only after this draft is fully
    published and therefore makes it cleanly stale through its stored timeline hash.
    """

    project = project_dir.expanduser().resolve()
    with score_mapping_transaction(project):
        return _build_project_shared_guitar_chart_locked(project, arrangement=arrangement)


def load_current_shared_guitar_draft(
    project_dir: Path,
    *,
    arrangement: SharedGuitarRole,
) -> tuple[GuitarAuthoringChart, SharedGuitarDraftManifest]:
    project = project_dir.expanduser().resolve()
    manifest_path = project / "charts" / f"{arrangement}_shared_timeline.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    try:
        timeline = load_current_shared_timeline(project)
        timeline_path = _shared_timeline_path(project)
        alignment = alignment_for_role(project, _role(arrangement))
        manifest = SharedGuitarDraftManifest.read_json(manifest_path)
    except (OSError, ValueError, ValidationError) as exc:
        raise ValueError(f"shared {arrangement} draft is not current: {exc}") from exc
    if manifest.arrangement != arrangement:
        raise ValueError(f"shared {arrangement} draft manifest has the wrong arrangement")
    if manifest.recording_sha256 != timeline.recording_sha256:
        raise ValueError(f"shared {arrangement} draft recording is stale")
    if manifest.score_sha256 != timeline.score_sha256:
        raise ValueError(f"shared {arrangement} draft score is stale")
    if manifest.shared_timeline_sha256 != sha256_file(timeline_path):
        raise ValueError(f"shared {arrangement} draft timing transform is stale")
    if manifest.source_track_index != alignment.track_index:
        raise ValueError(f"shared {arrangement} draft track mapping is stale")
    if manifest.position_review_sha256 != current_reviewed_positions_sha256(project):
        raise ValueError(f"shared {arrangement} draft reviewed-position layer is stale")
    if manifest.event_timing_review_sha256 != current_reviewed_event_timing_sha256(project):
        raise ValueError(f"shared {arrangement} draft reviewed-event-timing layer is stale")
    if manifest.technique_review_sha256 != current_reviewed_techniques_sha256(project):
        raise ValueError(f"shared {arrangement} draft reviewed-technique layer is stale")
    if manifest.chord_review_sha256 != current_reviewed_chords_sha256(project):
        raise ValueError(f"shared {arrangement} draft reviewed-chord layer is stale")
    source_path = _safe_project_file(project, project / manifest.source_path)
    if manifest.composed_source_track_indices is None:
        if manifest.composed_fanout_record_sha256 is not None:
            raise ValueError(f"shared {arrangement} draft composition binding is inconsistent")
        if source_path != Path(alignment.source_path).expanduser().resolve():
            raise ValueError(f"shared {arrangement} draft source path is stale")
    else:
        if manifest.composed_fanout_record_sha256 is None:
            raise ValueError(f"shared {arrangement} draft composition binding is inconsistent")
        try:
            layer = load_current_score_role_composition_fanout(project)
        except ValueError as exc:
            raise ValueError(f"shared {arrangement} draft composed source is stale: {exc}") from exc
        record = None if layer is None else layer.record_for(_role(arrangement))
        if record is None or list(record.source_track_indices) != manifest.composed_source_track_indices:
            raise ValueError(f"shared {arrangement} draft composed source track set is stale")
        if _record_content_sha256(record) != manifest.composed_fanout_record_sha256:
            raise ValueError(f"shared {arrangement} draft composed source content is stale")
    if sha256_file(source_path) != manifest.source_content_sha256:
        raise ValueError(f"shared {arrangement} draft source content is stale")
    chart_path = _safe_project_file(project, project / manifest.chart_path)
    if sha256_file(chart_path) != manifest.chart_sha256:
        raise ValueError(f"shared {arrangement} draft chart content changed after generation")
    chart = GuitarAuthoringChart.model_validate_json(chart_path.read_text(encoding="utf-8"))
    if chart.arrangement != arrangement or chart.source_sha256 != timeline.score_sha256:
        raise ValueError(f"shared {arrangement} chart provenance is stale")
    return chart, manifest


def shared_guitar_draft_is_current(project_dir: Path, arrangement: SharedGuitarRole) -> bool:
    try:
        load_current_shared_guitar_draft(project_dir, arrangement=arrangement)
    except (OSError, ValueError, ValidationError):
        return False
    return True
