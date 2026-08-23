from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .design_tokens import StatusState, format_status
from .validation import format_actionable_warning_summary
from .validation_dashboard import ValidationDashboardRow


class ValidationRowPresentation(BaseModel):
    """Presentation-only status text for one validation dashboard row."""

    model_config = ConfigDict(frozen=True)

    status_state: StatusState
    dashboard_text: str
    validation_text: str
    xml_text: str


_DASHBOARD_STATE_LABELS = {
    "BLOCKED": "Blocked",
    "VALIDATION_NEEDED": "Validation needed",
    "NOT_CONFIGURED": "Not configured",
    "XML_READY": "XML ready",
}


def _status_state(row: ValidationDashboardRow) -> StatusState:
    if row.state == "BLOCKED":
        return "fail"
    if row.state == "VALIDATION_NEEDED":
        return "review_required"
    if row.state == "NOT_CONFIGURED":
        return "info"
    if row.validation_state == "WARNING":
        return "warning"
    return "pass"


def _dashboard_detail(state: str) -> str:
    """Return a stable human label while preserving domain acronyms."""

    return _DASHBOARD_STATE_LABELS.get(state, state.replace("_", " ").title())


def present_validation_row(row: ValidationDashboardRow) -> ValidationRowPresentation:
    """Format validation authority without changing any underlying readiness state."""

    state = _status_state(row)
    dashboard_detail = _dashboard_detail(row.state)

    validation_state = row.validation_state.replace("_", " ").title()
    if row.validation_state in {"FAIL", "INVALID"}:
        validation_text = format_status("fail", validation_state)
    elif row.validation_state == "NOT_RUN":
        validation_text = format_status("review_required", "Not run")
    elif row.validation_state == "WARNING":
        # #375: never present the raw warning-event total on its own -- it can be
        # thousands of repeated events for one root cause. Pair it with the grouped
        # actionable count every time it is shown.
        warning_detail = (
            f"{validation_state} · {format_actionable_warning_summary(row.actionable_warning_count, row.warning_count)}"
            if row.warning_count
            else validation_state
        )
        validation_text = format_status("warning", warning_detail)
    else:
        validation_text = format_status("pass", validation_state)

    xml_text = (
        format_status("pass", "Rocksmith XML ready")
        if row.export_xml_ready
        else format_status("info", "Rocksmith XML not ready")
    )

    return ValidationRowPresentation(
        status_state=state,
        dashboard_text=format_status(state, dashboard_detail),
        validation_text=validation_text,
        xml_text=xml_text,
    )
