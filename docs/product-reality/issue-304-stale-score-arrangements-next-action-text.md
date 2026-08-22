# Product Reality defect: stale "confirm mappings" next-action text after confirmation

## Observed symptom

Reproduced during a packaged Windows Product Reality session (2026-08-20):
after human-confirming all three score mappings (Bass = Jason Newsted,
Lead = Kirk Hammett, Rhythm = James Hetfield), the "Song progress" panel
correctly advanced to `22% prepared — Ready to continue automatically` and
all three mapping rows showed as confirmed. The top guidance text next to
that headline, however, still read `Ready next: Confirm which score tracks
are Bass, Lead, and Rhythm. Use Continue Automatically.` — an instruction to
do something that was already done, immediately beside a headline that
correctly said the project was ready to proceed automatically instead.

## Root cause

`workflow_plan.py` reuses one `step_id` (`"score-arrangements"`) for several
distinct planner sub-states as a project moves through score mapping:
"add a score", "repair a broken score", "confirm proposed mappings", "wait
for score rights review", "fan out confirmed mappings" (`ready`, automatic),
and "fanned out" (`complete`). Each sub-state already carries its own
accurate `WorkflowStep.title`/`reason` describing exactly what is happening.

`song_readiness._friendly_action()`, however, mapped the next actionable
step to user-facing text purely by `step_id` via a fixed `_FRIENDLY_TITLES`
lookup, ignoring which sub-state the step was actually in. Because every
`score-arrangements` sub-state shares the same `step_id`,
`_friendly_action()` always rendered the fixed
`"Confirm which score tracks are Bass, Lead, and Rhythm"` title — including
for the automatic "ready to fan out" sub-state that exists specifically
*because* every mapping was already confirmed. The `kind`/headline
("Ready to continue automatically") were computed correctly from the step's
own `mode`/`status`, so only the detail text was stale — masking, rather
than reflecting, the correct underlying planner state.

## Fix

`song_readiness._friendly_action()` now only applies the fixed
`_FRIENDLY_TITLES` override for `"score-arrangements"` when the computed
`kind` is `"needs_you"` (the one sub-state — "confirm proposed mappings" —
that text actually describes). For every other `"score-arrangements"`
sub-state (`waiting` or `automatic`), it falls back to the planner's own
state-specific `step.title` (e.g. `"Fan out confirmed score arrangements"`,
`"Wait for score rights/provenance review"`, `"Repair registered complete
score"`), which was already accurate and just wasn't being shown. No other
step_id was changed, and the human-confirmation gate itself, its routing,
and the underlying planner logic are unchanged.

## Regression protection

`tests/test_song_readiness.py` adds:

- `test_confirmed_score_arrangements_ready_to_fan_out_does_not_show_stale_confirm_text`
  — reproduces the exact reported scenario (a `score-arrangements` step in
  the `ready`/`automatic` "fan out" sub-state) and asserts the next-action
  title is the state-specific fan-out text, not the stale confirm text, in
  both `SongReadiness.next_action.title` and
  `GuidedDesktopApp.readiness_display()`'s rendered detail string.
- `test_score_arrangements_waiting_on_rights_review_uses_state_specific_title`
  — same defect class for the other non-`needs_you` sub-state
  (`blocked`/`automatic`, waiting on score rights review).
- `test_score_arrangements_still_confirmed_needs_you_uses_friendly_confirm_title`
  — confirms the one sub-state the friendly override is meant for
  (`blocked`/`human`, mappings not yet confirmed) is unaffected.

All three fail against the pre-fix `_friendly_action()` and pass after the
fix; the full existing `tests/test_song_readiness.py` suite (18 tests total)
continues to pass unchanged.

## Safety / authority boundary

Presentation-only text selection. No workflow routing, mapping-confirmation
logic, provenance, validation, human-review-gate semantics, or packaging
behavior changed.

## Residual risk

`"align-tab"` and `"human-review"` also multiplex `mode`/`kind` across
sub-states for the same `step_id`, but their existing friendly titles are
generic enough (`"Align the score to the recording"`, `"Review the
generated song draft"`) that they remain reasonably accurate in every
observed sub-state; they were intentionally left unchanged in this pass to
keep the fix narrowly scoped to the exact reported defect. If a similar
stale-text report surfaces for either of those steps, cross-link it here
rather than treating it as unrelated.
