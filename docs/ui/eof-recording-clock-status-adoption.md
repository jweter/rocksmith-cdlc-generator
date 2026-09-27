# EOF recording-clock verdict design-token adoption

This #305 slice is the fifth real-screen adoption of the desktop design-system
foundation introduced in PR #340, following the validation dashboard (#341),
the Score & Mappings role status labels (#352), the Review Queue severity
column (#353), and the track-trust panel.

## What changed

Song Workspace's "Editor on Fire reference" panel
(`eof_workspace_ui.py`, `build_eof_recording_clock_workspace_status`)
previously rendered the EOF recording-clock comparison verdict as a bare
`"PASS"`/`"REVIEW"` word embedded in plain sentence text, with no color,
symbol, or weight differentiation -- the exact gap `docs/ui/desktop-ui-audit.md`
named this EOF panel for before any #305 adoption slice existed.

The recording-clock status label now renders through the shared semantic
status registry (`✓ PASS`, `◉ REVIEW REQUIRED`) ahead of the existing detail
sentence, and the label's foreground color is set to match. The
classification lives in the new, tkinter-free
`eof_recording_clock_status_presentation.py`
(`present_eof_recording_clock_status()`) so it can be regression-tested
without constructing a Tk root or requiring a display server, mirroring
`track_trust_status_presentation.py` and `score_mapping_status_presentation.py`.
`eof_workspace_ui.py` remains responsible only for assembling the detail
sentence from the current `EOFRecordingClockComparison` and for widget
construction/refresh.

`report.matched` maps to the shared vocabulary as: `True` (the EOF-observed
timeline agrees with the final promoted recording clock within tolerance) →
`pass`; `False` → `review_required` rather than `fail`, since EOF comparison
is advisory-only evidence to inspect, never itself a blocking failure. The
two non-verdict branches (no comparison run yet, and a stale/unavailable
report) are left with the theme-default label color rather than being
force-classified into the verdict vocabulary they do not belong to.

## Authority boundary

This is presentation-only. It does not change `report.matched`, the
recording-clock comparison itself, or any packaging/validation gate. EOF
evidence remains advisory-only and never changes chart authority
automatically, exactly as before this change.

## Accessibility

Color is never the sole signal: a matched comparison renders `✓ PASS` and a
mismatch renders `◉ REVIEW REQUIRED` -- the symbol + label text alone already
communicates the state even with no styling applied at all. The label's
foreground color (resolved through `desktop_theme.status_dark_foreground`,
tuned for this app's dark theme rather than the light-background tokens in
`design_tokens.status_style(...).foreground`) is reinforcement only.

## Remaining #305 "Areas to review" surfaces

Not yet adopted in a real screen as of this slice: Song Workspace layout and
information density (partially covered by `song_workspace_health_presentation.py`),
source audio and score/tab import cards (partially covered by
`source_rights_status_presentation.py`), progress indicators for long-running
local operations, error/empty/loading states and recovery actions, and
High-DPI/Windows-11-scaling behavior (all unconfirmed without packaged human
testing).
