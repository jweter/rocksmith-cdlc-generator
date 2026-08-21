# Product Reality defect: audio-only Bass evidence became hard mapping failures

## Observed symptom

During a packaged Windows Product Reality session for Metallica - 08 The Call of Ktulu (Remastered), the workflow reached 13/15 steps and stopped with many Bass validation failures of the form `Bass note N has no playable string/fret position.`

## Root cause

Symbolic/audio reconciliation intentionally retains unmatched `audio_only` detections as review evidence. `map_reconciled_bass_chart()` then treated every reconciled entry, including `audio_only`, as authoritative Bass chart content and sent it through fret mapping. Full-mix detector artifacts outside the four-string Bass fretboard therefore became `unmapped_bass_note` structural failures instead of remaining source-disagreement warnings.

## Fix

Exclude `audio_only` reconciliation entries from authoritative Bass fret mapping while preserving them in `review/source_disagreements.json`, where ADR-015 already defines reconciliation disagreements as explicit human-review warnings.

## Regression protection

`tests/test_reconciled_mapping.py` now covers an out-of-range `audio_only` detection beside a valid symbolic note and verifies that the evidence remains in the reconciled chart while only symbolic-authority content reaches the mapped Bass chart.

## Residual risk

This fix addresses evidence-only detections being promoted into chart content. Any remaining `unmapped_bass_note` failures after re-running the Product Reality project should be investigated separately as genuine symbolic tuning/fret-range problems rather than assumed to share this root cause.

## Follow-up: stale mapping artifact masked the fix (found in retest, fixed separately)

Retesting the fixed packaged build against the *same* project reproduced the identical historical `unmapped_bass_note` failures. That was not evidence the algorithm fix above was wrong: `charts/bass_mapped.json` had been materialized by the pre-fix algorithm, and the workflow planner treated its mere file existence as "mapping complete," so the corrected `map_reconciled_bass_chart()` was never re-run against the existing project.

This is the recurring stale-derivative-state pattern tracked in #193 ("Stale derivative/readiness state after upstream authority changes"). The corrective pattern applied:

- `BassMapping` now carries a `mapping_algorithm_version` (see `fret_mapping.CURRENT_BASS_MAPPING_ALGORITHM_VERSION`), stamped on every freshly generated mapping.
- `fret_mapping.bass_mapping_is_current()` reads a persisted mapping and fails closed as stale both when the version field is absent (mappings written before this field existed) and when it does not match the current algorithm version.
- `workflow_plan.build_project_workflow_plan()` uses this check for the `map-bass` step instead of raw file existence, so a stale mapping is reported `ready` (with the regeneration command) rather than `complete`. Re-running `map-bass` already invalidates dependent validation/EOF/package artifacts (`mapping_pipeline._invalidate_bass_mapping_derivatives`), so fixing the planner's status check is sufficient to make the automatic workflow runner and the GUI both regenerate and revalidate correctly.

Regression coverage: `tests/test_fret_mapping.py::test_mapping_missing_algorithm_version_field_is_stale` and related cases; `tests/test_workflow_plan.py::test_stale_bass_mapping_reopens_map_bass_step`.

A packaged-app retest of the same representative project is still required to confirm the post-#322 mapping algorithm itself produces zero (or a materially smaller, individually justified) set of `unmapped_bass_note` failures once the planner actually offers regeneration.
