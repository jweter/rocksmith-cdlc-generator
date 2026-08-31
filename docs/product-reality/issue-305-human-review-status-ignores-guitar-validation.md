# Product Reality defect: combined Bass+guitar human-review step reports ready/complete before Lead/Rhythm validation finishes

## Observed symptom

Static code audit of `multi_arrangement_plan.py`'s combined Bass+guitar
planning path (`build_multi_arrangement_workflow_plan`, the branch taken
once a confirmed Bass mapping and at least one confirmed guitar role both
exist) found that it inserts `validate-lead`/`validate-rhythm`
`WorkflowStep`s directly ahead of the `human-review` step, but never
updates `human-review`'s own `status` field to account for them.

That field is inherited unchanged from `build_project_workflow_plan`
(`workflow_plan.py`), where it is computed solely from Bass's own
`review/validation_report.json` artifact:

```python
status="ready" if validation else "blocked",
```

`validation` there only ever checks the Bass validation report. It has no
knowledge of `review/lead_validation_report.json` /
`review/rhythm_validation_report.json`
(`_guitar_validation_path`), which the newly inserted `validate-<role>`
steps track.

Concretely: once Bass has already been validated once, `human-review`
carries `status="ready"` from that point on, even after a human
subsequently confirms a Lead or Rhythm score mapping whose own
`validate-<role>` step is still `"blocked"` or freshly `"ready"`-but-unrun.

`song_readiness.build_song_readiness`'s `_counts_as_progress_complete`
treats a `human-review` step with `status="ready"` as progress-complete
for the "N% prepared" percentage, so the guided shell's headline percentage
overstated how finished the project actually was. The *next actionable
step* itself stayed correct (`validate-lead`/`validate-rhythm` still
precede `human-review` in step order, so `song_readiness`'s "first
unresolved required step" logic already surfaced them ahead of
`human-review`) -- this defect was specifically in the completion
percentage, not in which action the user was told to do next.

## Root cause

`build_multi_arrangement_workflow_plan`'s combined-path branch reuses the
Bass-only plan's steps largely unmodified and only *inserts* new
`validate-<role>` steps for the confirmed guitar roles; it never revisits
the pre-existing `human-review` step's status now that those new steps
exist. `_build_guitar_only_plan` (the guitar-only, no-Bass branch) already
computes its own `human-review` status correctly from a
`validations_complete` accumulator over its guitar roles -- the combined
path was the one branch that never got the equivalent treatment.

## Fix

`multi_arrangement_plan.py`: while building the `validate-<role>` steps for
the combined path, accumulate `guitar_validations_complete` the same way
`_build_guitar_only_plan` already does. After inserting those steps, if
`human-review` is still `status="ready"` but `guitar_validations_complete`
is `False`, replace it with a copy carrying `status="blocked"` and a reason
explaining it is waiting on Lead/Rhythm validation. No mapping, alignment,
validation, or human-review-gate authority logic changed; this only
corrects the `human-review` step's own status field so it reflects the
steps now inserted ahead of it.

## Regression coverage

`tests/test_multi_arrangement_plan.py`:

- `test_human_review_waits_for_guitar_validation_even_when_bass_already_validated`
  builds a base plan with Bass already fully validated and `human-review`
  at `status="ready"`, confirms Lead and Rhythm with current-but-unvalidated
  drafts, and asserts `validate-lead`/`validate-rhythm` are `"ready"` while
  `human-review` is now `"blocked"`.

Targeted suite: `uv run pytest tests/test_multi_arrangement_plan.py
tests/test_song_readiness.py tests/test_workflow_plan.py
tests/test_song_workspace_shared_timeline_promotion_ui.py -q` -> 43 passed.
Full suite: `uv run pytest -q` -> 1642 passed, 4 failed (the 4 failures are
`test_bass_transcriber.py`/`test_beat_trackers.py` cases requiring the
optional `librosa` beat-analysis extra, which is not installed in this
sandbox; confirmed unrelated to this change and matching the prior verified
baseline of 1642 passing tests).
