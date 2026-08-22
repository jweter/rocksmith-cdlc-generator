from __future__ import annotations

"""Pure presentation logic for the Song Workspace Review Queue tab's per-row severity.

This is a #305 slice: the desktop UI audit (``docs/ui/desktop-ui-audit.md``) found
that status text like ``"PASS"``/``"FAIL"``/``"WARNING"`` renders everywhere as plain,
unstyled text, so "nothing helps a user visually scan a busy panel for the FAIL rows
-- every status looks identical regardless of severity". The Review Queue tab's
``Severity`` column (``SongWorkspaceWindow._build_review_queue`` /
``_refresh_review_queue`` in ``song_workspace_ui.py``) is exactly that: a plain
``WorkspaceReviewItem.severity`` string (``"INFO"``/``"WARNING"``/``"FAIL"``) with no
color, symbol, or weight differentiation, even though the validation dashboard
(#341) and the Score & Mappings role status (#352) already establish the pattern this
module mirrors for a third real screen: turn domain state into a semantic
``StatusState`` plus ready-to-render text/tag in a tkinter-free module, so the
classification stays unit-testable without a display server.

This module defines no new review authority. ``WorkspaceReviewItem.severity`` already
carries the persisted validation/review finding as plain data; this only maps that
existing value to the shared semantic status vocabulary so it can be rendered with the
same non-color-alone (symbol + label + color) treatment used everywhere else.
"""

from pydantic import BaseModel, ConfigDict

from .design_tokens import StatusState, format_status

#: WorkspaceReviewItem.severity is Literal["INFO", "WARNING", "FAIL"]; INFO findings
#: are informational review context rather than an accepted/passing state, so they map
#: to "info" rather than "pass" -- nothing in this panel represents a passing review.
_SEVERITY_TO_STATUS_STATE: dict[str, StatusState] = {
    "FAIL": "fail",
    "WARNING": "warning",
    "INFO": "info",
}


class ReviewQueueRowPresentation(BaseModel):
    """Presentation-only status for one Review Queue tab row."""

    model_config = ConfigDict(frozen=True)

    status_state: StatusState
    severity_text: str


def present_review_queue_row_severity(severity: str) -> ReviewQueueRowPresentation:
    """Classify one persisted ``WorkspaceReviewItem.severity`` value for display.

    Unrecognized severity values (defensive only -- the model's ``Literal`` type
    already constrains normal callers) fall back to ``"info"`` rather than raising,
    so a future/unexpected severity still renders instead of breaking the tab.
    """

    state = _SEVERITY_TO_STATUS_STATE.get(severity, "info")
    return ReviewQueueRowPresentation(status_state=state, severity_text=format_status(state))
