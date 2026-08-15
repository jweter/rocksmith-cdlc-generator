from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .song_workspace import ArrangementWorkspaceState, SongWorkspaceSnapshot

DashboardState = Literal[
    "NOT_CONFIGURED",
    "VALIDATION_NEEDED",
    "BLOCKED",
    "VALIDATED",
    "XML_READY",
]


class ValidationDashboardRow(BaseModel):
    """Read-only validation summary for one Rocksmith arrangement."""

    model_config = ConfigDict(frozen=True)

    role: Literal["bass", "lead", "rhythm"]
    configured: bool
    state: DashboardState
    validation_state: str
    fail_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    export_xml_ready: bool
    next_action: str


class ValidationDashboardSummary(BaseModel):
    """Aggregate state shown by the desktop validation dashboard."""

    model_config = ConfigDict(frozen=True)

    rows: list[ValidationDashboardRow]
    configured_count: int = Field(ge=0)
    blocked_count: int = Field(ge=0)
    validation_needed_count: int = Field(ge=0)
    xml_ready_count: int = Field(ge=0)

    @property
    def headline(self) -> str:
        if not self.configured_count:
            return "No Rocksmith arrangements are configured."
        if self.blocked_count:
            return f"{self.blocked_count} configured arrangement(s) blocked by validation."
        if self.validation_needed_count:
            return f"{self.validation_needed_count} configured arrangement(s) still need validation."
        if self.xml_ready_count == self.configured_count:
            return "All configured arrangements are validated and have current Rocksmith XML."
        return "All configured arrangements are validated; export work remains."


def _row_for(arrangement: ArrangementWorkspaceState) -> ValidationDashboardRow:
    if not arrangement.configured:
        return ValidationDashboardRow(
            role=arrangement.role,
            configured=False,
            state="NOT_CONFIGURED",
            validation_state=arrangement.validation_state,
            fail_count=arrangement.fail_count,
            warning_count=arrangement.warning_count,
            export_xml_ready=False,
            next_action="Enable this arrangement in the project before validation is required.",
        )

    if arrangement.validation_state == "INVALID":
        return ValidationDashboardRow(
            role=arrangement.role,
            configured=True,
            state="BLOCKED",
            validation_state=arrangement.validation_state,
            fail_count=arrangement.fail_count,
            warning_count=arrangement.warning_count,
            export_xml_ready=False,
            next_action=arrangement.validation_problem
            or "Persisted validation evidence is invalid; re-run validation before export.",
        )

    if arrangement.validation_state == "FAIL":
        return ValidationDashboardRow(
            role=arrangement.role,
            configured=True,
            state="BLOCKED",
            validation_state=arrangement.validation_state,
            fail_count=arrangement.fail_count,
            warning_count=arrangement.warning_count,
            export_xml_ready=False,
            next_action=(
                f"Resolve {arrangement.fail_count} validation failure(s) in the review queue, then validate again."
            ),
        )

    if arrangement.validation_state == "NOT_RUN":
        return ValidationDashboardRow(
            role=arrangement.role,
            configured=True,
            state="VALIDATION_NEEDED",
            validation_state=arrangement.validation_state,
            fail_count=0,
            warning_count=0,
            export_xml_ready=False,
            next_action="Run the normal validation step after the current arrangement draft is ready.",
        )

    if arrangement.export_xml_ready:
        return ValidationDashboardRow(
            role=arrangement.role,
            configured=True,
            state="XML_READY",
            validation_state=arrangement.validation_state,
            fail_count=arrangement.fail_count,
            warning_count=arrangement.warning_count,
            export_xml_ready=True,
            next_action="Current validation and Rocksmith XML are ready for downstream build flow.",
        )

    return ValidationDashboardRow(
        role=arrangement.role,
        configured=True,
        state="VALIDATED",
        validation_state=arrangement.validation_state,
        fail_count=arrangement.fail_count,
        warning_count=arrangement.warning_count,
        export_xml_ready=False,
        next_action="Validation is current; complete or refresh Rocksmith XML export before packaging.",
    )


def build_validation_dashboard(snapshot: SongWorkspaceSnapshot) -> ValidationDashboardSummary:
    """Summarize existing validation authority without creating or promoting any authority."""

    rows = [_row_for(arrangement) for arrangement in snapshot.arrangements]
    configured = [row for row in rows if row.configured]
    return ValidationDashboardSummary(
        rows=rows,
        configured_count=len(configured),
        blocked_count=sum(row.state == "BLOCKED" for row in configured),
        validation_needed_count=sum(row.state == "VALIDATION_NEEDED" for row in configured),
        xml_ready_count=sum(row.state == "XML_READY" for row in configured),
    )
