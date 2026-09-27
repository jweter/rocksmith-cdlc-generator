from __future__ import annotations

"""Pure presentation logic for the Editor on Fire recording-clock comparison verdict
shown in Song Workspace's "Editor on Fire reference" panel.

This is a #305 slice: `docs/ui/desktop-ui-audit.md` named the EOF panel as one of the
places `"PASS"`/`"REVIEW"`-shaped verdict text renders as a plain, unstyled string with
no color, symbol, or weight differentiation -- the same gap already closed for the
validation dashboard (#341), the Score & Mappings role status (#352), the Review Queue
severity column (#353), and the track-trust panel. This module mirrors that precedent
for a fifth real screen: turn the existing `matched` boolean into a semantic
`StatusState` plus ready-to-render text in a tkinter-free module, so the classification
stays unit-testable without a display server.

This module defines no new EOF comparison authority. `EOFRecordingClockComparison`
already carries the current match/mismatch verdict as plain data (see
`eof_recording_clock.py`); this only maps that existing value to the shared semantic
status vocabulary so it renders with the same non-color-alone (symbol + label + color)
treatment used everywhere else. EOF evidence remains advisory-only and never changes
chart authority -- this module changes no behavior other than how the same verdict is
displayed.
"""

from pydantic import BaseModel, ConfigDict

from .design_tokens import StatusState, format_status


class EOFRecordingClockStatusPresentation(BaseModel):
    """Presentation-only status for the EOF recording-clock comparison verdict."""

    model_config = ConfigDict(frozen=True)

    status_state: StatusState
    text: str


def present_eof_recording_clock_status(
    *, matched: bool, detail: str
) -> EOFRecordingClockStatusPresentation:
    """Classify an EOF recording-clock comparison verdict for #305 status presentation.

    `matched` is the existing `EOFRecordingClockComparison`-derived verdict boolean
    (`report.matched`); `detail` is the already-assembled instrument/classification/
    delta/error/observation-count sentence, preserved verbatim so no information is
    lost -- only the leading symbol/label/color changes. A match is `pass`; a mismatch
    is `review_required` (evidence to inspect, not itself a hard failure) rather than
    `fail`, since EOF comparison is advisory-only and never itself blocks anything.
    """

    state: StatusState = "pass" if matched else "review_required"
    return EOFRecordingClockStatusPresentation(
        status_state=state, text=format_status(state, detail)
    )
