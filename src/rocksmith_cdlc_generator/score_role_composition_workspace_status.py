from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .hashing import sha256_file
from .reconciliation import ReconciledBassChart
from .score_fanout import ScoreFanoutManifest
from .score_mapping_review import load_score_for_mapping_review
from .score_role_composition_fanout_review import (
    load_current_score_role_composition_fanout,
    preview_score_role_composition_overlaps,
)
from .score_role_composition_overlap import CompositionOverlap
from .score_role_composition_review import load_current_score_role_composition
from .score_source import ArrangementRole, ProjectScoreSource
from .shared_guitar import SharedGuitarRole, load_current_shared_guitar_draft

CompositionWorkspaceState = Literal[
    "unmapped",
    "single_track",
    "multi_track_pending",
    "multi_track_composed",
]

# Whether the *built* per-role draft currently reflects the role's composition intent
# above. This is a distinct question from ``CompositionWorkspaceState``: a role can be
# ``multi_track_composed`` (the fan-out layer has a current composed note stream) while
# its built draft is still stale because it has not been rebuilt yet, or was built before
# the composition selection last changed. Lead/Rhythm read this from
# ``SharedGuitarDraftManifest``. Bass has no persisted draft manifest analogous to that --
# its fan-out output flows directly into ``reconcile_project_bass``/``ReconciledBassChart``
# instead of a cached, re-loadable draft -- so Bass reads ``charts/bass_reconciled.json``
# as its draft equivalent instead; see ``_bass_draft_status``.
DraftWorkspaceState = Literal[
    "not_applicable",
    "not_built",
    "current_single_track",
    "current_composed",
    "stale",
]

_ROLE_ORDER = {"lead": 0, "rhythm": 1, "bass": 2}
_SHARED_GUITAR_ROLES: dict[ArrangementRole, SharedGuitarRole] = {
    ArrangementRole.lead: "lead",
    ArrangementRole.rhythm: "rhythm",
}


class ScoreRoleCompositionWorkspaceItem(BaseModel):
    """Read-only Song Workspace status for one role's current composition intent."""

    model_config = ConfigDict(frozen=True)

    arrangement: Literal["bass", "lead", "rhythm"]
    primary_source_track_index: int | None = Field(default=None, ge=0)
    primary_source_track_name: str | None = None
    selected_source_track_indices: list[int] = Field(default_factory=list)
    selected_source_track_names: list[str | None] = Field(default_factory=list)
    available_source_track_indices: list[int] = Field(default_factory=list)
    available_source_track_names: list[str | None] = Field(default_factory=list)
    is_multi_track: bool
    state: CompositionWorkspaceState
    overlap_count: int | None = Field(default=None, ge=0)
    overlaps: list[CompositionOverlap] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    draft_state: DraftWorkspaceState = "not_applicable"
    draft_stale_detail: str | None = None


class ScoreRoleCompositionWorkspaceStatus(BaseModel):
    """Read-only control model for score role composition review in Song Workspace."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    plan_stale_detail: str | None = None
    fanout_stale_detail: str | None = None
    roles: list[ScoreRoleCompositionWorkspaceItem] = Field(default_factory=list)

    def role_item(
        self, arrangement: Literal["bass", "lead", "rhythm"]
    ) -> ScoreRoleCompositionWorkspaceItem | None:
        return next((item for item in self.roles if item.arrangement == arrangement), None)


def _project(project_dir: Path) -> Path:
    project = project_dir.expanduser().resolve()
    if not (project / "project.json").is_file():
        raise FileNotFoundError(f"Not a CDLC project: {project}")
    return project


def _track_name(score: ProjectScoreSource, index: int | None) -> str | None:
    if index is None:
        return None
    return next((track.name for track in score.tracks if track.source_track_index == index), None)


def _bass_composed_output_path(project: Path, score: ProjectScoreSource) -> Path:
    # Mirrors score_fanout.py::_materialize_composed_bass_source's output path exactly.
    return (
        project
        / "sources"
        / "imported"
        / "composition"
        / f"bass-composed-{score.source_sha256[:12]}.json"
    )


def _current_bass_fanout_output(
    project: Path, score: ProjectScoreSource
) -> tuple[Path, str] | None:
    """Best-effort: the current Bass fan-out output's project-relative path and content hash.

    Returns ``None`` when no fan-out manifest exists yet, it is unreadable/corrupt, it has
    no Bass entry, or the entry's output file is missing -- mirroring every other
    best-effort check in this module rather than raising.
    """

    manifest_path = project / "sources" / "imported" / f"score-fanout-{score.source_sha256[:12]}.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = ScoreFanoutManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, ValidationError):
        return None
    entry = next((item for item in manifest.arrangements if item.role is ArrangementRole.bass), None)
    if entry is None:
        return None
    output_path = project / entry.output_json
    if not output_path.is_file():
        return None
    try:
        return output_path, sha256_file(output_path)
    except OSError:
        return None


def _bass_draft_status(
    project: Path, *, score: ProjectScoreSource, primary_index: int | None
) -> tuple[DraftWorkspaceState, str | None]:
    """Best-effort Bass equivalent of ``_draft_status``, reading ``ReconciledBassChart``.

    Bass has no persisted draft manifest analogous to ``SharedGuitarDraftManifest`` -- its
    fan-out output flows directly into ``reconcile_project_bass``/``ReconciledBassChart``
    instead of a cached, re-loadable draft. ``charts/bass_reconciled.json`` is read as that
    draft here. It is treated as current using exactly the same identity check
    ``score_fanout.py::_invalidate_stale_bass_derivatives`` uses to decide whether a prior
    reconciliation survives a new fan-out: matching registered score, matching confirmed
    primary track index, and a matching content hash of the *current* Bass fan-out output
    (``ReconciledBassChart.source_content_sha256``). A composed Bass fan-out is
    materialized directly into the score fan-out manifest (unlike Lead/Rhythm, whose
    composed output lives only inside the shared-guitar chart-build path), so once the
    content hash matches, whether the reconciliation reflects a composed or single-track
    selection is read directly off which output file that content hash belongs to, rather
    than off the *current* composition selection -- a composition edited after the last
    fan-out/reconciliation run correctly leaves this reporting what was actually built,
    with ``CompositionWorkspaceState`` elsewhere already surfacing that composition intent
    has moved on.
    """

    path = project / "charts" / "bass_reconciled.json"
    if not path.is_file():
        return "not_built", None
    try:
        reconciliation = ReconciledBassChart.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, ValidationError) as exc:
        return "stale", str(exc)

    current_output = _current_bass_fanout_output(project, score)
    matches = (
        current_output is not None
        and reconciliation.source_sha256 == score.source_sha256
        and reconciliation.track_index == primary_index
        and reconciliation.source_content_sha256 is not None
        and reconciliation.source_content_sha256 == current_output[1]
    )
    if not matches:
        return "stale", (
            "Bass reconciliation does not match the current registered score, confirmed "
            "primary track, or fan-out output content; rerun cdlc-score-fanout and Bass "
            "reconciliation"
        )
    output_path, _content_sha256 = current_output  # current_output is not None here
    is_composed = output_path.resolve() == _bass_composed_output_path(project, score).resolve()
    return ("current_composed" if is_composed else "current_single_track"), None


def _draft_status(
    project: Path, role: ArrangementRole, *, score: ProjectScoreSource, primary_index: int | None
) -> tuple[DraftWorkspaceState, str | None]:
    """Best-effort read of whether role's built draft is current.

    Never raises: a missing draft is ``not_built`` and any staleness reason is surfaced as
    ``stale`` with ``draft_stale_detail`` rather than propagated, mirroring every other
    best-effort check in this module.
    """

    if role is ArrangementRole.bass:
        return _bass_draft_status(project, score=score, primary_index=primary_index)

    shared_arrangement = _SHARED_GUITAR_ROLES.get(role)
    if shared_arrangement is None:
        return "not_applicable", None
    try:
        _chart, manifest = load_current_shared_guitar_draft(project, arrangement=shared_arrangement)
    except FileNotFoundError:
        return "not_built", None
    except ValueError as exc:
        return "stale", str(exc)
    if manifest.composed_source_track_indices is not None:
        return "current_composed", None
    return "current_single_track", None


def inspect_score_role_composition_workspace_status(
    project_dir: Path,
) -> ScoreRoleCompositionWorkspaceStatus:
    """Describe current multi-track composition plan/overlap/fan-out state per role.

    This mirrors ``track_trust_workspace_status.inspect_track_trust_workspace_status``:
    it never records a selection, resolves an overlap, composes a note stream, or
    mutates project files. A role with no confirmed primary mapping is reported
    ``unmapped``. A role with no persisted composition selection beyond its confirmed
    primary track is reported ``single_track`` — the existing single-track fan-out
    remains authoritative and there is nothing to compose. A role with more than one
    currently selected track and no persisted composed fan-out matching that exact
    selection is reported ``multi_track_pending`` with the live overlap count a human
    must resolve before composing. A role whose persisted composed fan-out already
    matches its current selection is reported ``multi_track_composed``.

    A stale/corrupt persisted composition plan or fan-out record is surfaced via
    ``plan_stale_detail``/``fanout_stale_detail`` rather than raised, so Song Workspace
    can explain what needs explicit human attention instead of the whole status call
    failing.

    Each mapped role also reports ``available_source_track_indices``/``_names``: every
    score track not currently in that role's selection, so a Song Workspace track picker
    can offer them without a separate score read. A ``multi_track_pending`` role also
    reports the exact ``overlaps`` evidence (verbatim ``CompositionOverlap`` entries from
    ``preview_score_role_composition_overlaps``) so a Song Workspace overlap-decision UI
    can present each finding without a separate overlap read; this never resolves an
    overlap or picks a default on its own.
    """

    project = _project(project_dir)
    score = load_score_for_mapping_review(project)

    plan_stale_detail: str | None = None
    try:
        plan = load_current_score_role_composition(project)
    except (OSError, ValueError) as exc:
        plan = None
        plan_stale_detail = str(exc)

    fanout_stale_detail: str | None = None
    try:
        fanout = load_current_score_role_composition_fanout(project)
    except (OSError, ValueError) as exc:
        fanout = None
        fanout_stale_detail = str(exc)

    items: list[ScoreRoleCompositionWorkspaceItem] = []
    for role in sorted(ArrangementRole, key=lambda item: _ROLE_ORDER[item.value]):
        mapping = score.mapping_for(role)
        if mapping is None or not mapping.human_confirmed:
            items.append(
                ScoreRoleCompositionWorkspaceItem(
                    arrangement=role.value,
                    is_multi_track=False,
                    state="unmapped",
                    blockers=[f"{role.value} has no human-confirmed primary score mapping yet"],
                )
            )
            continue

        primary_index = mapping.source_track_index
        selection = plan.selection_for(role) if plan is not None else None
        selected_indices = (
            list(selection.source_track_indices) if selection is not None else [primary_index]
        )
        is_multi_track = len(selected_indices) > 1
        selected_names = [_track_name(score, index) for index in selected_indices]
        available_indices = sorted(
            {track.source_track_index for track in score.tracks} - set(selected_indices)
        )
        available_names = [_track_name(score, index) for index in available_indices]

        blockers: list[str] = []
        overlap_count: int | None = None
        overlaps: list[CompositionOverlap] = []
        state: CompositionWorkspaceState
        if not is_multi_track:
            state = "single_track"
        else:
            record = fanout.record_for(role) if fanout is not None else None
            if record is not None and record.source_track_indices == selected_indices:
                state = "multi_track_composed"
            else:
                state = "multi_track_pending"
                try:
                    report = preview_score_role_composition_overlaps(project, role=role)
                except (OSError, ValueError) as exc:
                    blockers.append(str(exc))
                else:
                    summary = next((item for item in report.roles if item.role is role), None)
                    overlap_count = summary.overlap_count if summary is not None else 0
                    overlaps = list(summary.overlaps) if summary is not None else []

        draft_state, draft_stale_detail = _draft_status(
            project, role, score=score, primary_index=primary_index
        )

        items.append(
            ScoreRoleCompositionWorkspaceItem(
                arrangement=role.value,
                primary_source_track_index=primary_index,
                primary_source_track_name=_track_name(score, primary_index),
                selected_source_track_indices=selected_indices,
                selected_source_track_names=selected_names,
                available_source_track_indices=available_indices,
                available_source_track_names=available_names,
                is_multi_track=is_multi_track,
                state=state,
                overlap_count=overlap_count,
                overlaps=overlaps,
                blockers=blockers,
                draft_state=draft_state,
                draft_stale_detail=draft_stale_detail,
            )
        )

    return ScoreRoleCompositionWorkspaceStatus(
        plan_stale_detail=plan_stale_detail,
        fanout_stale_detail=fanout_stale_detail,
        roles=items,
    )
