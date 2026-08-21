from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .design_tokens import StatusState, format_status
from .validation_dashboard import ValidationDashboardRow


class ValidationRowPresentation(BaseModel):
    """Presentation-only status text for one validation dashboard row."""

    model_config = ConfigDict(frozen=True)

    status_state: StatusState
    dashboard_text: str
    validation_text: str
    xml_text: str


def _status_state(row: ValidationDashboardRow) -> StatusState:
    if row.state == "BLOCKED":
        return "fail"
    if row.state == "VALIDATION_NEEDED":
        return "review_required"
    if row.state == "NOT_CONFIGURED":
        return "info"
    if row.warning_count:
        return "warning"
    return "pass"


def present_validation_row(row: ValidationDashboardRow) -> ValidationRowPresentation:
    """Format validation authority without changing any underlying readiness state."""

    state = _status_state(row)
    dashboard_detail = row.state.replace("_", " ").title()

    validation_state = row.validation_state.replace("_", " ").title()
    if row.validation_state in {"FAIL", "INVALID"}:
        validation_text = format_status("fail", validation_state)
    elif row.validation_state == "NOT_RUN":
        validation_text = format_status("review_required", "Not run")
    elif row.warning_count:
        validation_text = format_status("warning", f"{validation_state} · {row.warning_count} warning(s)")
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
