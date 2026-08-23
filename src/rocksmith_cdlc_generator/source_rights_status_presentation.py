from __future__ import annotations

"""Pure presentation logic for the Song Workspace Sources tab's Recording and
Complete-score rights/provenance review status.

This is a #305 slice: the Sources tab's rights/provenance status
(``song_workspace_ui._refresh_sources``) still rendered as plain, unstyled text
embedded in a multi-line blob (``"Rights/provenance: reviewed"`` /
``"Rights/provenance: review required"``), unlike every other #305 surface --
the validation dashboard (#341), Score & Mappings role status (#352), Review
Queue severity (#353), and the track-trust panel (#356) all already turn their
domain state into a semantic ``StatusState`` plus ready-to-render text via a
small, tkinter-free module, so the classification stays unit-testable without a
display server. This module mirrors that identical pattern for the fourth --
now fifth -- real screen.

This module defines no new rights/provenance review authority. It only formats
the same ``recording_reviewed`` / ``score_reviewed`` fields the Sources tab
already reads from ``SongWorkspaceSourcesSnapshot`` as a proper semantic status
instead of plain suffix text. Source-rights decisions remain an explicit human
action elsewhere in the desktop app; this view stays read-only, exactly as
``_build_sources``'s existing disclosure label already states.
"""

from pydantic import BaseModel, ConfigDict

from .design_tokens import StatusState, format_status


class SourceRightsStatusPresentation(BaseModel):
    """Presentation-only status for one source's rights/provenance review state."""

    model_config = ConfigDict(frozen=True)

    status_state: StatusState
    text: str


def present_source_rights_status(*, registered: bool, reviewed: bool) -> SourceRightsStatusPresentation:
    """Classify one source's rights/provenance review state for #305 status presentation.

    - Not registered (the complete score is optional; the recording is always
      registered): informational, not actionable -- there is nothing to review yet.
    - Registered but not yet human-reviewed: review required. Registering a
      source is never itself a rights/provenance decision.
    - Registered and human-reviewed: pass.
    """

    if not registered:
        return SourceRightsStatusPresentation(
            status_state="info", text=format_status("info", "Not registered")
        )
    if reviewed:
        return SourceRightsStatusPresentation(status_state="pass", text=format_status("pass", "Reviewed"))
    return SourceRightsStatusPresentation(
        status_state="review_required",
        text=format_status("review_required", "Rights/provenance review required"),
    )
