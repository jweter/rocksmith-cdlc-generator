# Product Reality defect: Overview/Arrangements/Validation still present raw warning-event totals after queue grouping

## Observed symptom

Reproduced on a fresh packaged Windows build `v0.1.0 · 74bea6b8` of the
representative `For Whom the Bell Tolls` project: the Song Workspace Review
Queue tab correctly showed the grouped/actionable presentation queue from
#365/#366/#367 (19 actionable rows, 0 failures), but the Overview tab's
per-arrangement validation column, the Arrangements tab's Flags column, and
the Validation dashboard all still displayed raw warning-event totals —
Bass 2851, Lead 2046, Rhythm 2981 — with no indication that these were raw
evidence counts rather than remaining review work. A project that was
effectively fixed (19 actionable groups, 0 failures) read as if it still had
thousands of unresolved problems.

## Root cause

`_workspace_review_queue` (`validation.py`, from #365/#366) and the
read-time migration in `song_workspace._read_validation` (#367) only ever
collapsed the **queue** (`ValidationReport.review_queue` /
`SongWorkspaceSnapshot.review_queue`) into grouped rows. They never touched
`ValidationReport.warning_count`, which stays the exact raw count on
purpose (it is the audit/provenance authority total). That raw count is
exactly what `ArrangementWorkspaceState.warning_count` copies
(`song_workspace.py`), and every consuming surface — the Overview tree's
validation cell, the Arrangements tab's Flags column, the Validation
dashboard's Warnings column and status text, and both `validation.py`'s and
`guitar_validation.py`'s `summary.md` — rendered that one raw number with no
paired context and no distinction from "distinct root causes remaining".
There was no field anywhere carrying "how many actionable groups does this
raw total collapse to", so no surface could show it.

## Fix

- `validation.py` gains `count_actionable_warnings(items)` (counts distinct
  `(severity, stage, code)` WARNING groups via the existing
  `summarize_review_queue`), `format_actionable_warning_summary(actionable,
  raw)` (the shared long-form "N actionable warning groups · M underlying
  warning events" phrasing), and `format_actionable_warning_compact(...)`
  (the "N/M" form for narrow table cells). `guitar_validation.py` reuses the
  same helpers instead of duplicating the phrasing.
- `ArrangementWorkspaceState` (`song_workspace.py`) gains
  `actionable_warning_count`, computed per role from the same (already
  grouped, per #367) `report.review_queue` used to populate the combined
  Review Queue. `SongWorkspaceSnapshot` gains `raw_warning_event_count`, the
  exact sum of every arrangement's raw `warning_count`. Both are additive
  fields; `warning_count`/`fail_count` are completely unchanged.
- `ValidationDashboardRow` (`validation_dashboard.py`) carries the same
  `actionable_warning_count` through to the desktop Validation dashboard.
- Song Workspace Overview, Arrangements, Review Queue, and the Validation
  dashboard (`song_workspace_ui.py`, `validation_dashboard_ui.py`,
  `validation_dashboard_presentation.py`) now render the actionable count
  alongside the raw total everywhere a warning count is shown, using the
  same shared vocabulary ("actionable warning group(s)" / "underlying
  warning event(s)", or the compact "actionable/raw" form in table cells).
  `review/summary.md` and `review/{arrangement}_summary.md` do the same for
  their `**Warnings:**` line.
- FAIL counts were never grouped and remain fully untouched and explicit in
  every surface (never merged into the warning pairing).

This is presentation/count-plumbing only. `ValidationReport.warning_count`,
`fail_count`, `status`, `can_package`, `flags.json`, and every existing
grouping/migration behavior from #365/#366/#367 are unchanged; nothing is
auto-accepted and no human review gate is weakened.

## Regression protection

- `tests/test_validation.py`: `test_count_actionable_warnings_groups_repeated_events_by_root_cause`,
  `test_format_actionable_warning_summary_preserves_raw_total_alongside_groups`,
  `test_format_actionable_warning_compact_pairs_actionable_with_raw`, and
  `test_summary_markdown_pairs_actionable_groups_with_raw_warning_total`
  (2851 raw events collapsing to 1 actionable group, with the full raw list
  still intact in `flags.json`).
- `tests/test_guitar_validation_export.py::test_guitar_summary_pairs_actionable_groups_with_raw_warning_total`
  proves Lead/Rhythm's `summary.md` uses the identical phrasing as Bass.
- `tests/test_song_workspace.py::test_workspace_pairs_actionable_warning_groups_with_raw_event_totals`
  reproduces the exact reported shape across two arrangements (Bass: 1 FAIL +
  2851 raw warnings -> 1 actionable group; Lead: 2046 raw warnings across 3
  root causes -> 3 actionable groups) and asserts raw totals, actionable
  counts, and the combined grouped queue all reconcile exactly with no
  double counting and no dropped events, while the FAIL count stays
  individually explicit.
- `tests/test_validation_dashboard.py` and
  `tests/test_validation_dashboard_presentation.py` cover propagation onto
  the dashboard row and its rendered text (raw 2851 vs. actionable 3, both
  present, neither substituted for the other).
- `tests/test_song_workspace_arrangement_warning_presentation_ui.py` (new)
  and updates to `tests/test_song_workspace_review_queue_ui.py` exercise the
  actual Song Workspace UI refresh methods (`_refresh_arrangements`,
  `_refresh_review_queue`) directly against lightweight fakes, following the
  existing `SimpleNamespace` + unbound-method pattern used elsewhere in this
  window's tests.

The full project test suite (1337 tests with `dev`+`beat` extras installed
on Python 3.12) passes unchanged otherwise.

## Safety / authority boundary

Purely presentational plus additive read-only count fields. No validation
rule, severity, priority, packaging eligibility, grouping/migration
behavior, or human review gate changed. Raw warning-event totals remain
fully intact for audit/provenance in `warning_count`,
`raw_warning_event_count`, and `flags.json`; nothing is deleted, hidden, or
auto-accepted.

## Residual risk

Other, not-yet-audited desktop surfaces that read `warning_count` directly
in the future should pair it with `actionable_warning_count` (or the shared
`format_actionable_warning_summary`/`format_actionable_warning_compact`
helpers) rather than reintroducing a bare raw total, to avoid regressing
this same defect class.
