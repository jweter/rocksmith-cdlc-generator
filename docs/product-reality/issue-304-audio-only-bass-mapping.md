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
