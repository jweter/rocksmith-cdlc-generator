# Shared Timeline v1

## Goal

A project with one recording and one complete reviewed score should discover song timing once. Bass, Lead, and Rhythm must not maintain independent score-to-recording timelines when they are projections of the same score.

Shared Timeline v1 introduces a project-level timing authority at:

`analysis/shared_timeline.json`

The contract is keyed to both immutable identities that matter:

- the project recording SHA-256;
- the registered complete score SHA-256.

It also pins the exact content SHA-256 of the authoritative Bass fan-out JSON used to establish the transform. This prevents a later importer/fan-out run from silently changing symbolic timing beneath an already-reviewed timeline while keeping the same path, score SHA, role, and track index.

It stores the reviewed piecewise score-to-recording transform, its anchors/regions/confidence/warnings, the human-confirmed Bass mapping used as the alignment authority, and every currently human-confirmed arrangement role that inherits the transform.

## Review boundary

Automatic beat-grid alignment remains evidence, not acceptance. The timeline is created only by an explicit human action:

```text
cdlc-shared-timeline promote PROJECT
```

Project-generated `analysis/alignment.json` records the recording SHA-256 it was calculated against. Promotion succeeds only when that recording identity still matches the project, the alignment is against the current authoritative Bass output from the current `score-fanout-<sha>.json` manifest, and that Bass mapping is human-confirmed. Legacy alignment files without recording identity must be regenerated before promotion.

Promotion shares the same OS-backed score transaction lock as mapping confirmation and score fan-out. A remap or fan-out therefore cannot race timeline publication.

## Arrangement inheritance

`alignment_for_role(PROJECT, role)` materializes an arrangement-specific `AlignmentReport` view from the one shared transform. Bass, Lead, and Rhythm receive the same anchors, regions, offset, recording identity, confidence, and residual statistics while retaining their own current fan-out source path and confirmed source-track index.

This is deliberately different from aligning each arrangement separately. Arrangement-specific note/chord reconciliation remains downstream work, but song structure and score-to-recording timing are shared.

## Staleness rules

A stored shared timeline is rejected unless all of the following still match:

- current project recording SHA-256;
- current registered score SHA-256;
- current complete fan-out manifest;
- current human-confirmed arrangement role set;
- authority role and track mapping;
- current authority fan-out output path;
- exact SHA-256 content identity of the authority fan-out output.

The file may remain on disk after a later remap or fan-out, but consumers must load it through `load_current_shared_timeline`, which fails closed when any authority identity has changed.

## Current boundary

Shared Timeline v1 establishes and verifies the one song-level timing authority and exposes inheritance views for Bass, Lead, and Rhythm.

The next milestone is to wire Lead and Rhythm chart construction/workflow planning directly to these inherited alignment views so users no longer run separate alignment commands for guitar arrangements.
