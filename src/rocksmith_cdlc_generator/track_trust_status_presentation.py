from __future__ import annotations

"""Pure presentation logic for the Song Workspace "Human-reviewed source track
trust" panel's Bass/Lead/Rhythm status.

This is a #305 slice: `docs/ui/desktop-ui-audit.md` found that status text like
`"PASS"`/`"FAIL"`/`"WARNING"` renders everywhere as plain, unstyled text, and the
same gap applies here -- `TrackTrustWorkspaceControl.review_state`
(`"unreviewed"`/`"current"`/`"stale"`) was rendered by `track_trust_workspace_ui.py`
as a bare sentence with no color, symbol, or weight differentiation, even though the
validation dashboard (#341), the Score & Mappings role status (#352), and the Review
Queue severity column (#353) already establish the pattern this module mirrors for a
fourth real screen: turn domain state into a semantic ``StatusState`` plus
ready-to-render text in a tkinter-free module, so the classification stays
unit-testable without a display server.

This module defines no new track-trust review authority. ``review_state`` already
carries the current human-provenance decision as plain data (see
``track_trust_workspace_status.py`` / ``source_track_trust_review.py``); this only
maps that existing value to the shared semantic status vocabulary so it renders with
the same non-color-alone (symbol + label + color) treatment used everywhere else.
"""

from pydantic import BaseModel, ConfigDict

from .design_tokens import StatusState, format_status
from .track_trust_workspace_controls import TrackTrustWorkspaceControl

#: TrackTrustWorkspaceControl.review_state is Literal["unreviewed", "current", "stale"].
#: "current" is an explicit human acceptance of the present track source, so it maps to
#: "pass"; "stale" keeps the shared STALE styling (color plus italic) used everywhere
#: else a prior acceptance no longer covers the current derived state; "unreviewed"
#: means no human decision has been recorded yet, which is review-required rather than
#: a failure.
_REVIEW_STATE_TO_STATUS_STATE: dict[str, StatusState] = {
    "current": "pass",
    "stale": "stale",
    "unreviewed": "review_required",
}


class TrackTrustStatusPresentation(BaseModel):
    """Presentation-only status for one Bass/Lead/Rhythm track-trust panel state."""

    model_config = ConfigDict(frozen=True)

    status_state: StatusState
    text: str


def present_track_trust_status(control: TrackTrustWorkspaceControl) -> TrackTrustStatusPresentation:
    """Classify one track-trust control's ``review_state`` for #305 status presentation.

    The existing human-readable detail (arrangement, track name, note count, and
    ``control.status_text``) is preserved verbatim as the formatted detail so no
    information is lost -- only the leading symbol/label/color changes.
    """

    state = _REVIEW_STATE_TO_STATUS_STATE[control.review_state]
    label = control.arrangement.title()
    track_name = control.source_track_name or f"track {control.source_track_index}"
    detail = f"{label} · {track_name} · {control.note_count} notes · {control.status_text}"
    return TrackTrustStatusPresentation(status_state=state, text=format_status(state, detail))
