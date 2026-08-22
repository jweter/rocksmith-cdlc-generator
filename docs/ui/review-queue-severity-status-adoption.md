# Review Queue tab severity design-token adoption

This #305 slice is the third real-screen adoption of the desktop design-system
foundation introduced in PR #340, following the validation dashboard (#341)
and the Score & Mappings role status labels (#352).

## What changed

The Song Workspace's Review Queue tab (`song_workspace_ui.py`,
`_build_review_queue` / `_refresh_review_queue`) previously rendered each row's
`Severity` column as the raw `WorkspaceReviewItem.severity` string
(`"FAIL"`/`"WARNING"`/`"INFO"`) with no color, symbol, or weight
differentiation — exactly the gap the desktop UI audit's finding #2 named:
"nothing helps a user visually scan a busy panel for the FAIL rows — every
status looks identical regardless of severity."

Each row's Severity cell now renders through the shared semantic status
registry (`✗ FAIL`, `⚠ WARNING`, `ℹ INFO`), and the row itself carries a
matching Treeview tag so `_build_review_queue`'s
`tag_configure(state, foreground=...)` calls color the whole row consistent
with the validation dashboard's existing per-row-tag pattern.

The severity-to-status classification lives in the new, tkinter-free
`review_queue_row_presentation.py` (`present_review_queue_row_severity()`) so
it can be regression-tested without constructing a Tk root or requiring a
display server, mirroring `validation_dashboard_presentation.py` and
`score_mapping_status_presentation.py`. `song_workspace_ui.py` remains
responsible only for widget construction/refresh.

## Authority boundary

This is presentation-only. It does not change which findings are persisted,
which items are queued for review, review priority/ordering, the underlying
`WorkspaceReviewItem.severity` value, or any packaging/validation gate. The
row-selection/locate-on-timeline behavior (`_selected_review_item`) still maps
Treeview row `iid` back to the same `snapshot.review_queue` index it always
did; only the displayed severity text and row tag changed.

## Accessibility

Color is never the sole signal: `INFO` renders `ℹ INFO`, `WARNING` renders
`⚠ WARNING`, and `FAIL` renders `✗ FAIL` — the symbol + label text alone
already communicates severity even with no styling applied at all. Row
foreground color (via the Treeview tag) is reinforcement only.

## Remaining #305 "Areas to review" surfaces

Not yet adopted in a real screen as of this slice: Song Workspace layout and
information density, source audio and score/tab import cards, progress
indicators for long-running local operations, error/empty/loading states and
recovery actions, and High-DPI/Windows-11-scaling behavior (all unconfirmed
without packaged human testing).
