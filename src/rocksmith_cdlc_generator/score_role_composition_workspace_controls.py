from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .score_mapping_review import load_score_for_mapping_review
from .score_role_composition_fanout_review import (
    compose_and_persist_score_role_composition_fanout,
)
from .score_role_composition_overlap_review import ScoreRoleCompositionOverlapDecisionPlan
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

    return ScoreRoleCompositionWorkspaceControl(
        arrangement=item.arrangement,
        is_multi_track=item.is_multi_track,
        state=item.state,
        overlap_count=item.overlap_count,
        status_text=status_text,
        compose_button_text=_COMPOSE_BUTTON_TEXT if item.state != "multi_track_composed" else "Composed",
        compose_button_enabled=compose_button_enabled,
        blocker_text=blocker_text,
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
