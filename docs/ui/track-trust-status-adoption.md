# Track trust panel status design-token adoption

This #305 slice is the fourth real-screen adoption of the desktop design-system
foundation introduced in PR #340, following the validation dashboard (#341),
the Score & Mappings role status labels (#352), and the Review Queue severity
column (#353).

## What changed

The Song Workspace's "Human-reviewed source track trust" panel
(`track_trust_workspace_ui.py`, `_refresh_track_trust_panel`) previously
rendered `TrackTrustWorkspaceControl.review_state`
(`"unreviewed"`/`"current"`/`"stale"`) only as plain sentence text (e.g. "Lead
source trust is current for Lead Guitar" vs. "...has not been explicitly
accepted...") with no color, symbol, or weight differentiation -- the same gap
the desktop UI audit named for other panels before their own #305 adoption
slices.

The panel's status line now renders through the shared semantic status
registry (`✓ PASS`, `⏳ STALE`, `◉ REVIEW REQUIRED`) ahead of the existing
detail text, and the status label's foreground color is set to match. The
classification lives in the new, tkinter-free `track_trust_status_presentation.py`
(`present_track_trust_status()`) so it can be regression-tested without
constructing a Tk root or requiring a display server, mirroring
`score_mapping_status_presentation.py` and `review_queue_row_presentation.py`.
`track_trust_workspace_ui.py` remains responsible only for widget
construction/refresh.

`review_state` maps to the shared vocabulary as: `"current"` (an explicit,
still-valid human acceptance) → `pass`; `"stale"` → `stale` (color plus
italic, consistent with every other STALE presentation in the app); and
`"unreviewed"` (no human decision recorded yet) → `review_required`. The two
pre-existing non-review-state branches -- no role selected, and the panel
failing to load status -- are left with the theme-default label color rather
than being force-classified into the review-state vocabulary they do not
belong to.

## Authority boundary

This is presentation-only. It does not change `review_state` itself, which
arrangement roles can be accepted, the underlying
`record_track_source_trust_acceptance` acceptance write, or any packaging/
validation gate. `_accept_track_source_trust` and
`accept_track_source_from_workspace` are unchanged.

## Accessibility

Color is never the sole signal: `current` renders `✓ PASS`, `stale` renders
`⏳ STALE`, and `unreviewed` renders `◉ REVIEW REQUIRED` -- the symbol + label
text alone already communicates the state even with no styling applied at
all. The label's foreground color is reinforcement only.

## Remaining #305 "Areas to review" surfaces

Not yet adopted in a real screen as of this slice: Song Workspace layout and
information density, source audio and score/tab import cards, progress
indicators for long-running local operations, error/empty/loading states and
recovery actions, and High-DPI/Windows-11-scaling behavior (all unconfirmed
without packaged human testing).
