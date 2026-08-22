# Product Reality defect: Review Queue detail panel shows stale "no findings" text beside visible FAIL rows

## Observed symptom

Reproduced during a packaged Windows Product Reality session (2026-08-20):
after safe automation reached 13/15 workflow steps (87%), project health
became `BLOCKED` and the Review Queue tab's tree table showed many Bass
mapping `FAIL` rows (`Bass note N has no playable string/fret position.`).
The detail label directly beneath that same tree table, however, still read
`No persisted validation findings are currently queued.` — an obviously
inconsistent pairing: a visibly populated FAIL/WARNING table next to a label
claiming nothing is queued.

## Root cause

`SongWorkspaceWindow._refresh_review_queue()` (`song_workspace_ui.py`)
rebuilds `review_tree` from `snapshot.review_queue` on every `refresh()`
call, which unconditionally clears any existing row selection along with the
old rows. The `review_detail_var` label below the tree, however, was only
ever updated in two places:

- inside `_refresh_review_queue()`, and only in the `if not
  snapshot.review_queue:` branch (the empty-queue case), and
- inside `_review_selected()`, fired only by a `<<TreeviewSelect>>` event
  when the user clicks a row.

So the very first time a project's review queue was empty (e.g. before
validation had produced any findings, which is the common early-project
state), `review_detail_var` was set to `"No persisted validation findings
are currently queued."` and then never touched again by any later refresh
that populated the queue with real FAIL/WARNING rows — because rebuilding
the tree does not fire a `<<TreeviewSelect>>` event, and the non-empty
branch of `_refresh_review_queue()` did nothing to the label at all. The
stale empty-queue message survived indefinitely until the user happened to
click a row.

This is the same defect *class* already tracked under #193/ERR-2026-001
(cached/derived state that is not recomputed when its underlying data
changes) applied to a UI label instead of a persisted artifact: the label
was conditionally set for one state transition and left stale for every
other subsequent refresh.

## Fix

`_refresh_review_queue()` now sets `review_detail_var` on every refresh
call, for both branches:

- empty queue: unchanged `"No persisted validation findings are currently
  queued."`;
- non-empty queue: a summary reflecting the just-rendered tree state, e.g.
  `"1 items queued (1 failures · 0 warnings). Select a row to see
  details."`, replacing whatever text (stale or otherwise) was previously
  shown.

Selecting a specific row still overrides this summary with that row's full
detail via the existing `_review_selected()` handler, unchanged. No
workflow routing, validation logic, provenance, or review-queue contents
changed — this is presentation-only, matching the same safety boundary as
the prior stale-next-action-text fix (#349).

## Regression protection

`tests/test_song_workspace_review_queue_ui.py` (new) exercises
`SongWorkspaceWindow._refresh_review_queue` directly against a lightweight
fake `review_tree`/`review_detail_var`, following the existing
`SimpleNamespace` + unbound-method pattern used elsewhere for this module's
Tk-free UI tests (see `tests/test_timing_review_shared_promotion_ui.py`):

- `test_review_detail_reflects_populated_queue_not_a_stale_empty_message`
  — reproduces the exact reported sequence (empty-queue refresh, then a
  refresh with FAIL rows and no row selected) and asserts the stale empty
  message is gone and the detail label reflects the populated queue. This
  is the only one of the three tests that actually fails against the
  pre-fix `_refresh_review_queue()`; it passes after the fix.
- `test_review_detail_still_reports_empty_queue_when_queue_stays_empty`
  — passes both before and after this change, since the empty-queue branch
  it exercises is unchanged. It is a guard against a future regression to
  that branch, not a reproduction of this defect.
- `test_review_detail_counts_warnings_and_failures_separately` — new
  coverage for the count-summary logic this fix introduces; there is no
  pre-fix equivalent to compare against, since that logic did not exist
  before this change.

The full existing `tests/test_song_workspace.py` suite and the full project
test suite continue to pass unchanged.

## Safety / authority boundary

Presentation-only label text. No workflow routing, mapping/validation
logic, provenance, human-review-gate semantics, or packaging behavior
changed; the review queue's actual contents and the row-selection detail
view are unaffected.

## Residual risk

This fix addresses the specific label reported in the Product Reality
session. Other Song Workspace summary labels that are conditionally set in
only one branch of their refresh path could share the same staleness risk;
none were identified as reproducibly stale in this pass, but a future
report of a similarly "stuck" summary label in this window should be
cross-linked here and to #193 rather than treated as unrelated.
