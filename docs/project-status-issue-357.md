# Temporary continuity note — issue #357

The current Product Reality blocker is issue #357: a user who auditions the detector beat grid and finds it correct unchanged cannot currently confirm timing because `review/reviewed_timing.json` does not exist and promotion assumes an edited/locked review artifact.

Branch `agent/fix-357-unchanged-timing-confirmation` changes `promote_reviewed_timing()` so an unchanged detector map is materialized and human-confirmed on demand, while edited timing still requires a locked anchor. Regression coverage is in `tests/test_timing_review.py`.

After this fix merges and the Windows Desktop artifact is green, resume the same packaged For Whom the Bell Tolls project at Song Workspace → Timeline → Confirm beat edits → Promote shared song timing.

`docs/project-status.yaml` should be reconciled with live repository state in the next status-hygiene pass; at branch creation it still described now-merged PR #356 as open.
