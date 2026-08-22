# Track trust review-status design-token adoption

This #305 slice is the fourth real-screen adoption of the desktop
design-system foundation introduced in PR #340, following the validation
dashboard (#341), the Score & Mappings role status labels (#352), and the
Review Queue tab severity labels (#353).

## What changed

The Song Workspace's "Human-reviewed source track trust" panel
(`track_trust_workspace_ui.py`'s `_build_arrangement_preview` /
`_refresh_track_trust_panel`) previously rendered its per-role status text
as a plain, unstyled `ttk.Label` — the same "status is plain, unstyled text
only" gap the desktop UI audit's finding #2 named for every other panel
before adoption began.

`track_trust_workspace_controls.py`'s `TrackTrustWorkspaceControl` now
carries an explicit `status_state` field alongside the existing
`review_state`, computed by a small, tkinter-free mapping in
`_present_item()`:

| `review_state` (domain authority, `track_trust_workspace_status.py`) | `status_state` (#305 semantic) |
| --- | --- |
| `unreviewed` | `review_required` |
| `current` | `pass` |
| `stale` | `stale` |

`status_text` is now produced through `design_tokens.format_status(...)`
instead of a bare f-string, so it always carries a symbol + label (e.g.
`✓ PASS — Lead track trust current for Lead Track (12 events).`). The panel
label's foreground is recolored to `design_tokens.status_style(...)`'s color
on every refresh, mirroring the plain-`foreground`-only pattern
`desktop_app.py` already established for the Score & Mappings role labels
(`_set_mapping_status`) rather than the `ttk.Style`/Treeview-tag pattern used
for the validation dashboard and Review Queue tables — this panel is a single
label, not a table, so the simpler mechanism is the correct fit. States with
no semantic meaning yet (no project context, no role selected, or a status
load error) reset the label to ttk's default color instead of implying a
false pass/warning/fail/stale state.

## Authority boundary

This is presentation-only. It does not change `TrackTrustWorkspaceItem`,
`review_state` classification, `can_accept`/blocker eligibility, or the
underlying `record_track_source_trust_acceptance` write path — acceptance is
still refused server-side for any ineligible control regardless of what the
label displays. Only the displayed status text and label color changed.

## Accessibility

Color is never the sole signal: every `status_text` value renders its symbol
and uppercase label (`◉ REVIEW REQUIRED`, `✓ PASS`, `⏳ STALE`) before any
styling is applied, and `STALE` keeps its existing italic treatment so a
stale review layer stays visually unmistakable even without color.

## Remaining #305 "Areas to review" surfaces

Not yet adopted in a real screen as of this slice: Song Workspace layout and
information density, source audio and score/tab import cards, progress
indicators for long-running local operations, error/empty/loading states and
recovery actions, and High-DPI/Windows-11-scaling behavior (all unconfirmed
without packaged human testing).
