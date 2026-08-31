# Product Reality defect: guided "Next Step" button routes automatic-waiting sub-states of shared step_ids to a review tab with nothing to review

## Observed symptom

Static code audit of the shipped `cdlc-desktop` guided shell
(`GuidedDesktopApp.guided_action_spec`, `guided_desktop.py`) found that its
`routes` table is keyed only by `step_id` (`"score-arrangements"`,
`"align-tab"`, `"shared-timeline"`, `"source-rights"`, `"human-review"`),
without checking whether the current `ReadinessAction`'s `kind` is actually
`"needs_you"`.

`song_readiness.py`'s own `_friendly_action` already documents (see its
comment above the `score-arrangements` title special-case) that several of
these step_ids are shared by the planner between a real human-decision
sub-state and one or more automatic-blocked "waiting on something else"
sub-states with the *same* `step_id`:

- `score-arrangements`, `mode="automatic"`, `status="blocked"`: the planner
  is waiting on the registered score's source-rights review to resolve
  before a confirmed-mapping fan-out can run (`workflow_plan.py` "Shared-score
  fan-out cannot run until the registered score's source-rights review is
  explicitly resolved."), or waiting to repair a broken registered score, or
  reporting an unsupported shared-score format -- none of these have
  anything left to confirm on the Score tab; the mappings are already
  human-confirmed.
- `align-tab`, `mode="automatic"`, `status="blocked"`: the planner is
  waiting on an earlier automatic step (e.g. Bass transcription) before
  alignment can run; there is nothing to review yet.

`build_song_readiness` correctly classifies both of these as
`ReadinessAction(kind="waiting", ...)` and its `headline` says "Waiting for
earlier steps to finish" -- but it still becomes `readiness.next_action`
(the `else` branch in `build_song_readiness` sets `next_action = actionable`
for `kind == "waiting"` too, not only for `"needs_you"`/`"automatic"`).

`guided_action_spec` receives that `"waiting"` action, skips its
`kind == "automatic"` special case, then falls straight into the
step_id-keyed `routes` lookup -- which has no `kind` guard at all -- and
returns the same `("Review Score Tracks", "score")` /
`("Open Song Review", "song-review")` route it would return for a genuine
human decision. `_update_guided_action` then enables the "Next Step" button
with that label. Clicking it (`_run_guided_action`) jumps to the Score tab
and focuses a mapping combo box that already has confirmed values -- or
opens Song Review with nothing new to act on -- instead of disabling the
button (which is the correct, already-implemented behavior for every other
`"waiting"` state whose step_id isn't in the `routes` table).

## Root cause

`guided_action_spec`'s `routes` table was written against the step_id
alone, before the planner grew multiple automatic-blocked sub-states that
reuse the same step_id as their human-decision counterpart (the same
sharing `song_readiness.py`'s `_friendly_action` already had to special-case
for its title text). The route table was never updated to match.

## Fix

`guided_desktop.py`: `guided_action_spec` now returns `None` immediately
for any `action.kind != "needs_you"` (the `"automatic"` case was already
handled above; `"waiting"` now returns `None` the same way an unmapped
`"needs_you"` step falls through to the generic "Show Workflow Details"
route -- except a `"waiting"` state has nothing to show a details route for
either, since there is no decision pending). `_update_guided_action` already
disables the "Next Step" button whenever `guided_action_spec` returns
`None`, so a waiting sub-state now correctly shows a disabled button instead
of a misleading enabled one.

No mapping, validation, provenance, or human-review-gate logic changed;
this is a guided-shell action-routing fix only.

## Regression coverage

`tests/test_song_readiness.py`:

- `test_guided_action_does_not_route_waiting_score_arrangements_to_review_tab`
  asserts a `mode="automatic"`/`status="blocked"` `score-arrangements` step
  produces `kind="waiting"` and `guided_action_spec` returns `None`.
- `test_guided_action_does_not_route_waiting_align_tab_to_review_tab` asserts
  the same for `align-tab`.
- `test_guided_action_still_routes_ready_align_tab_review` asserts a genuine
  `needs_you` sub-state of the same shared step_id (`align-tab`,
  `mode="human"`, `status="ready"`) still routes normally, so the fix
  narrows routing correctly rather than disabling it entirely.

Full suite: `python -m pytest -q` -> 1636 passed, 3 skipped, 6 failed (the 6
failures are pre-existing on `main`, confirmed unrelated to this change).
`python scripts/check_automation_readiness.py` passes.
