from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .score_mapping_review import load_score_for_mapping_review
from .score_role_composition_fanout_review import (
    compose_and_persist_score_role_composition_fanout,
)
from .score_role_composition_overlap_review import ScoreRoleCompositionOverlapDecisionPlan
from .score_role_composition_review import (
    load_current_score_role_composition,
    record_score_role_composition,
)
from .score_role_composition_workspace_status import (
    CompositionWorkspaceState,
    ScoreRoleCompositionWorkspaceItem,
    ScoreRoleCompositionWorkspaceStatus,
    inspect_score_role_composition_workspace_status,
)
from .score_source import ArrangementRole

ArrangementRoleName = Literal["bass", "lead", "rhythm"]

_COMPOSE_BUTTON_TEXT = "Compose From Selected Tracks"
_CLI_HINT = (
    "Resolve overlaps with `cdlc-score-composition overlaps`/`compose --decisions` "
    "before this role can be composed here."
)


class ScoreRoleCompositionTrackOption(BaseModel):
    """One score track a role's composition could add, presented for a picker widget."""

    model_config = ConfigDict(frozen=True)

    source_track_index: int = Field(ge=0)
    name: str | None = None
    label: str


class ScoreRoleCompositionWorkspaceControl(BaseModel):
    """UI-ready control state for one role's current multi-track composition status."""

    model_config = ConfigDict(frozen=True)

    arrangement: ArrangementRoleName
    is_multi_track: bool
    state: CompositionWorkspaceState
    overlap_count: int | None = Field(default=None, ge=0)
    status_text: str
    compose_button_text: str
    compose_button_enabled: bool
    blocker_text: str | None = None
    selected_track_indices: list[int] = Field(default_factory=list)
    selected_track_names: list[str | None] = Field(default_factory=list)
    available_tracks: list[ScoreRoleCompositionTrackOption] = Field(default_factory=list)
    removable_track_indices: list[int] = Field(default_factory=list)
    add_track_enabled: bool = False


class ScoreRoleCompositionWorkspaceControls(BaseModel):
    """Presentation/controller snapshot suitable for Song Workspace widgets."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    plan_stale_detail: str | None = None
    fanout_stale_detail: str | None = None
    controls: list[ScoreRoleCompositionWorkspaceControl] = Field(default_factory=list)

    def control_for(
        self, arrangement: ArrangementRoleName
    ) -> ScoreRoleCompositionWorkspaceControl | None:
        return next((item for item in self.controls if item.arrangement == arrangement), None)


def _track_list_text(item: ScoreRoleCompositionWorkspaceItem) -> str:
    names = [name or "unnamed track" for name in item.selected_source_track_names]
    return ", ".join(names) if names else "no track"


def _track_option_label(index: int, name: str | None) -> str:
    return f"{name} (track {index})" if name else f"Unnamed track {index}"


def _present_item(item: ScoreRoleCompositionWorkspaceItem) -> ScoreRoleCompositionWorkspaceControl:
    label = item.arrangement.title()
    tracks = _track_list_text(item)
    track_count = len(item.selected_source_track_indices)
    overlap_count = item.overlap_count or 0

    compose_button_enabled = False
    if item.state == "unmapped":
        status_text = f"{label} has no human-confirmed primary score mapping yet."
    elif item.state == "single_track":
        status_text = f"{label} uses its single confirmed source track ({tracks}); nothing to compose."
    elif item.state == "multi_track_composed":
        status_text = f"{label} is already composed from {track_count} tracks ({tracks})."
    elif overlap_count:
        status_text = (
            f"{label} has {track_count} tracks selected ({tracks}) with "
            f"{overlap_count} unresolved cross-track overlap(s)."
        )
    else:
        status_text = f"{label} has {track_count} tracks selected ({tracks}) with no overlaps to resolve."
        compose_button_enabled = True

    blockers = list(item.blockers)
    if item.state == "multi_track_pending" and overlap_count:
        blockers.append(_CLI_HINT)
    blocker_text = "; ".join(blockers) if blockers else None

    available_tracks = [
        ScoreRoleCompositionTrackOption(
            source_track_index=index, name=name, label=_track_option_label(index, name)
        )
        for index, name in zip(
            item.available_source_track_indices, item.available_source_track_names, strict=True
        )
    ]
    # The confirmed primary always occupies index 0 of the selection and can never be
    # removed here; only additional tracks after it are ever removable.
    removable_track_indices = list(item.selected_source_track_indices[1:])
    add_track_enabled = item.state != "unmapped" and bool(available_tracks)

    return ScoreRoleCompositionWorkspaceControl(
        arrangement=item.arrangement,
        is_multi_track=item.is_multi_track,
        state=item.state,
        overlap_count=item.overlap_count,
        status_text=status_text,
        compose_button_text=_COMPOSE_BUTTON_TEXT if item.state != "multi_track_composed" else "Composed",
        compose_button_enabled=compose_button_enabled,
        blocker_text=blocker_text,
        selected_track_indices=list(item.selected_source_track_indices),
        selected_track_names=list(item.selected_source_track_names),
        available_tracks=available_tracks,
        removable_track_indices=removable_track_indices,
        add_track_enabled=add_track_enabled,
    )


def present_score_role_composition_workspace_status(
    status: ScoreRoleCompositionWorkspaceStatus,
) -> ScoreRoleCompositionWorkspaceControls:
    """Convert the read-only status model into deterministic widget-ready state."""

    return ScoreRoleCompositionWorkspaceControls(
        plan_stale_detail=status.plan_stale_detail,
        fanout_stale_detail=status.fanout_stale_detail,
        controls=[_present_item(item) for item in status.roles],
    )


def build_score_role_composition_workspace_controls(
    project_dir: Path,
) -> ScoreRoleCompositionWorkspaceControls:
    """Inspect current authority and return deterministic Song Workspace controls."""

    return present_score_role_composition_workspace_status(
        inspect_score_role_composition_workspace_status(project_dir)
    )


def compose_role_composition_from_workspace(
    project_dir: Path,
    *,
    arrangement: ArrangementRoleName,
) -> ScoreRoleCompositionWorkspaceControls:
    """Compose one eligible role's currently selected tracks and return refreshed controls.

    This only proceeds when the current status reports the role pending composition with
    zero unresolved cross-track overlaps, so the workspace panel never has to collect
    overlap resolutions itself. A role with unresolved overlaps must still be composed via
    ``cdlc-score-composition compose --decisions``; that per-overlap decision UI is a
    separate follow-on slice of issue #232. The underlying compose implementation still
    independently reimports every selected track and revalidates rights, mapping, plan,
    and overlap-decision coverage at write time, so this precheck is user-facing guidance
    rather than an authority bypass.
    """

    controls = build_score_role_composition_workspace_controls(project_dir)
    control = controls.control_for(arrangement)
    if control is None:
        raise ValueError(f"Current score has no {arrangement} arrangement")
    if not control.compose_button_enabled:
        detail = control.blocker_text or control.status_text
        raise ValueError(f"Cannot compose {arrangement} from the workspace: {detail}")

    role = ArrangementRole(arrangement)
    score = load_score_for_mapping_review(project_dir)
    decisions = ScoreRoleCompositionOverlapDecisionPlan(
        score_sha256=score.source_sha256, score_format=score.source_format
    )
    compose_and_persist_score_role_composition_fanout(project_dir, role=role, decisions=decisions)
    return build_score_role_composition_workspace_controls(project_dir)


def _persist_score_composition_selection(
    project_dir: Path,
    *,
    role: ArrangementRole,
    track_indices: list[int],
) -> None:
    """Write one role's ordered track selection, preserving every other role's plan.

    Mirrors ``cdlc-score-composition plan-select``: ``record_score_role_composition``
    independently revalidates the current registered score, that ``track_indices[0]``
    is still the role's human-confirmed primary mapping, and that every index names a
    known score track. This helper only merges the edit into the rest of the persisted
    plan; it grants no additional authority.
    """

    current = load_current_score_role_composition(project_dir)
    selections: dict[ArrangementRole, list[int]] = {}
    if current is not None:
        for selection in current.selections:
            selections[selection.role] = list(selection.source_track_indices)
    selections[role] = list(track_indices)
    record_score_role_composition(project_dir, selections=selections)


def add_score_composition_track(
    project_dir: Path,
    *,
    arrangement: ArrangementRoleName,
    track_index: int,
) -> ScoreRoleCompositionWorkspaceControls:
    """Add one more score track to a role's selection and return refreshed controls.

    This only appends a track currently reported as available for the role (i.e. an
    existing score track not already selected, on a role that already has a confirmed
    primary mapping); ``record_score_role_composition`` independently revalidates the
    result. Adding a track never composes a note stream or resolves an overlap by
    itself — the role may move to ``multi_track_pending`` and require an explicit
    compose action afterward.
    """

    controls = build_score_role_composition_workspace_controls(project_dir)
    control = controls.control_for(arrangement)
    if control is None:
        raise ValueError(f"Current score has no {arrangement} arrangement")
    if not control.add_track_enabled:
        raise ValueError(f"Cannot add a track to {arrangement}: {control.status_text}")
    if track_index in control.selected_track_indices:
        raise ValueError(f"Track {track_index} is already selected for {arrangement}")
    available_indices = {option.source_track_index for option in control.available_tracks}
    if track_index not in available_indices:
        raise ValueError(f"Track {track_index} is not an available score track for {arrangement}")

    updated_indices = [*control.selected_track_indices, track_index]
    _persist_score_composition_selection(
        project_dir, role=ArrangementRole(arrangement), track_indices=updated_indices
    )
    return build_score_role_composition_workspace_controls(project_dir)


def remove_score_composition_track(
    project_dir: Path,
    *,
    arrangement: ArrangementRoleName,
    track_index: int,
) -> ScoreRoleCompositionWorkspaceControls:
    """Remove one previously added track from a role's selection and return refreshed controls.

    Only a track reported in ``removable_track_indices`` may be removed here, which
    excludes the role's confirmed primary track (always the first selected index) by
    construction, so this can never strip a role down to zero selected tracks or
    replace its primary. ``record_score_role_composition`` independently revalidates
    the result.
    """

    controls = build_score_role_composition_workspace_controls(project_dir)
    control = controls.control_for(arrangement)
    if control is None:
        raise ValueError(f"Current score has no {arrangement} arrangement")
    if track_index not in control.removable_track_indices:
        raise ValueError(
            f"Track {track_index} cannot be removed from {arrangement}'s composition "
            "(it is not a currently removable selected track)"
        )

    updated_indices = [index for index in control.selected_track_indices if index != track_index]
    _persist_score_composition_selection(
        project_dir, role=ArrangementRole(arrangement), track_indices=updated_indices
    )
    return build_score_role_composition_workspace_controls(project_dir)
