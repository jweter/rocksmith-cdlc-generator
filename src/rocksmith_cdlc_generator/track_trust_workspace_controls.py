from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .source_track_trust_review import record_track_source_trust_acceptance
from .track_trust_workspace_status import (
    TrackTrustWorkspaceItem,
    TrackTrustWorkspaceStatus,
    inspect_track_trust_workspace_status,
)

ArrangementRoleName = Literal["bass", "lead", "rhythm"]


class TrackTrustWorkspaceControl(BaseModel):
    """UI-ready control state for one explicit whole-track source-trust decision."""

    model_config = ConfigDict(frozen=True)

    arrangement: ArrangementRoleName
    source_track_index: int = Field(ge=0)
    source_track_name: str | None = None
    note_count: int = Field(ge=0)
    review_state: Literal["unreviewed", "current", "stale"]
    button_text: str
    button_enabled: bool
    status_text: str
    blocker_text: str | None = None
    acceptance_scope: Literal["imported_note_identity_and_positions"] = (
        "imported_note_identity_and_positions"
    )


class TrackTrustWorkspaceControls(BaseModel):
    """Presentation/controller snapshot suitable for Song Workspace widgets."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    stale_review_detail: str | None = None
    controls: list[TrackTrustWorkspaceControl] = Field(default_factory=list)

    def control_for(self, arrangement: ArrangementRoleName) -> TrackTrustWorkspaceControl | None:
        return next((item for item in self.controls if item.arrangement == arrangement), None)


def _present_item(item: TrackTrustWorkspaceItem) -> TrackTrustWorkspaceControl:
    label = item.source_track_name or f"track {item.source_track_index}"
    if item.review_state == "current":
        button_text = "Reaccept Track Source"
        status_text = (
            f"{item.arrangement.title()} source trust is current for {label} "
            f"({item.note_count} events)."
        )
    elif item.review_state == "stale":
        button_text = "Reaccept Current Track Source"
        status_text = (
            f"Prior {item.arrangement.title()} track trust is stale; the current {label} "
            "must be explicitly reviewed again."
        )
    else:
        button_text = "Accept Track Source"
        status_text = (
            f"{item.arrangement.title()} source trust has not been explicitly accepted for "
            f"{label} ({item.note_count} events)."
        )

    blocker_text = "; ".join(item.blockers) if item.blockers else None
    return TrackTrustWorkspaceControl(
        arrangement=item.arrangement,
        source_track_index=item.source_track_index,
        source_track_name=item.source_track_name,
        note_count=item.note_count,
        review_state=item.review_state,
        button_text=button_text,
        button_enabled=item.can_accept,
        status_text=status_text,
        blocker_text=blocker_text,
    )


def present_track_trust_workspace_status(
    status: TrackTrustWorkspaceStatus,
) -> TrackTrustWorkspaceControls:
    """Convert the read-only status model into deterministic widget-ready state."""

    return TrackTrustWorkspaceControls(
        stale_review_detail=status.stale_review_detail,
        controls=[_present_item(item) for item in status.tracks],
    )


def build_track_trust_workspace_controls(project_dir: Path) -> TrackTrustWorkspaceControls:
    """Inspect current authority and return deterministic Song Workspace controls."""

    return present_track_trust_workspace_status(inspect_track_trust_workspace_status(project_dir))


def accept_track_source_from_workspace(
    project_dir: Path,
    *,
    arrangement: ArrangementRoleName,
) -> TrackTrustWorkspaceControls:
    """Perform one explicit eligible track acceptance and return refreshed controls.

    The controller refuses disabled actions before invoking the provenance-bearing write.
    The underlying acceptance implementation still revalidates current score, mapping,
    fan-out, tuning, positions, and pitch consistency at write time, so this precheck is
    user-facing guidance rather than an authority bypass.
    """

    controls = build_track_trust_workspace_controls(project_dir)
    control = controls.control_for(arrangement)
    if control is None:
        raise ValueError(f"Current score fan-out has no {arrangement} arrangement")
    if not control.button_enabled:
        detail = control.blocker_text or "current track is not eligible for acceptance"
        raise ValueError(f"Cannot accept {arrangement} track source: {detail}")

    record_track_source_trust_acceptance(project_dir, arrangement=arrangement)
    return build_track_trust_workspace_controls(project_dir)
