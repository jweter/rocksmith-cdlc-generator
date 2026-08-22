from __future__ import annotations

"""Pure presentation logic for the Score & Mappings tab's Bass/Lead/Rhythm role
mapping status.

This is a #305 slice: "Bass/Lead/Rhythm role mapping status presentation outside
the validation dashboard" was explicitly called out in docs/project-status.yaml as
one of the still-unadopted #305 "Areas to review" surfaces. It mirrors the pattern
already established for the validation dashboard (see
``validation_dashboard_presentation.py``): a small, tkinter-free module that turns
domain state into a semantic ``StatusState`` plus ready-to-render text, so the
classification logic stays unit-testable without a display server and the UI module
only has to render it.

This module defines no new mapping/confirmation authority. It only formats the same
human-confirmation fields the Score & Mappings tab already tracks (a selected score
track, and whether that selection has been explicitly human-confirmed via
``confirm_score_mapping``) as a proper semantic status instead of plain suffix text.
"""

from pydantic import BaseModel, ConfigDict

from .design_tokens import StatusState, format_status


class MappingRoleStatusPresentation(BaseModel):
    """Presentation-only status for one Bass/Lead/Rhythm mapping row."""

    model_config = ConfigDict(frozen=True)

    status_state: StatusState
    text: str


def present_mapping_role_status(
    *, has_score: bool, has_selection: bool, human_confirmed: bool
) -> MappingRoleStatusPresentation:
    """Classify one arrangement role's mapping status for #305 status presentation.

    - No score registered yet: informational, not actionable.
    - A score is registered but no track is selected for this role: review required.
    - A track is selected but not yet human-confirmed: still review required --
      selecting a track is never itself confirmation (mappings are never
      auto-accepted; see ``desktop_app.confirm_mapping``).
    - A track is selected and human-confirmed: pass.
    """

    if not has_score:
        return MappingRoleStatusPresentation(
            status_state="info", text=format_status("info", "No score registered")
        )
    if human_confirmed:
        return MappingRoleStatusPresentation(status_state="pass", text=format_status("pass", "Confirmed"))
    if has_selection:
        return MappingRoleStatusPresentation(
            status_state="review_required",
            text=format_status("review_required", "Selected — needs Confirm"),
        )
    return MappingRoleStatusPresentation(
        status_state="review_required",
        text=format_status("review_required", "No track selected"),
    )
