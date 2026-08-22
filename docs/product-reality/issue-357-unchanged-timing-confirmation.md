# Issue #357 — unchanged detector timing cannot be confirmed

## Product Reality reproduction

Packaged Windows build `v0.1.0 · 007367ac` was tested with a fresh **For Whom the Bell Tolls** project. The user opened Song Workspace → Timeline, enabled the click/beat-grid audition, listened through the complete 5:10 recording, and reported that the detected beat grid remained spot-on for the whole song.

No timing correction was needed.

Clicking **Confirm beat edits** raised a modal containing only the missing path to `review/reviewed_timing.json`.

## Root cause

The timing-review UI deliberately loads `reviewed_timing.json` with `create=False` during refresh. When no beat has been nudged, locked, or otherwise edited, no reviewed-timing artifact exists. The click audition still works because playback falls back to the detector beat times.

`promote_reviewed_timing()` then loaded the reviewed artifact without `create=True`, so confirmation of an unchanged detector map failed with `FileNotFoundError`. It also required at least one locked anchor even when the user intentionally made no edits.

## Correct behavior

Unchanged detector timing is a valid human review outcome.

- If the user confirms timing without prior edits, create the reviewed-timing artifact from the current detector map.
- Permit that unchanged map to become human-confirmed without requiring an arbitrary locked anchor.
- If beat times were edited, continue requiring at least one locked anchor so edited timing retains explicit correction evidence.
- Preserve recording/tempo-map provenance checks and existing stale-review protections.

## Regression protection

The fix adds coverage for both sides of the boundary:

1. A fresh project with no `reviewed_timing.json` can promote unchanged detector timing; the artifact is created, marked human-confirmed, and becomes authoritative.
2. A modified reviewed map with no locked anchors is still rejected.

This is a normal-path Product Reality blocker, not a convenience feature.
