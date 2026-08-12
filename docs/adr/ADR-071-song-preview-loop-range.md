# ADR-071: Read-only Song Preview loop range

## Status

Accepted.

## Context

Milestone 11 requires selection-based looping before full audio transport and timing editing are introduced. The Song Preview layer already exposes a trusted snapshot, viewport projection, review queue, playhead state, fretboard state, and variable-tempo click schedule. The next transport-facing contract needs to represent a loop without altering canonical timing or imported musical data.

## Decision

Add a read-only `PreviewLoopRange` derived from `SongPreviewSnapshot`.

The range:

- stores explicit start/end timestamps and deterministic duration;
- records canonical beat timestamps falling inside the half-open loop interval;
- preserves full-snapshot beat indices instead of renumbering them for the selection;
- permits loop ranges with no beat markers so trailing audio or sparse regions remain representable;
- provides deterministic modulo wrapping for a future playhead/transport;
- leaves positions before the loop start unchanged to permit future pre-roll behavior.

## Boundaries

This contract does not start audio playback, change beat timing, create manual anchors, move notes, alter review state, mutate manifests or imported artifacts, package DLC, or touch the live Rocksmith installation or NoCableLauncher.

## Consequences

The future Song Workspace can represent and repeat an arbitrary user-selected time range while keeping the authoritative beat grid untouched. Audio-device behavior and editable timing remain separate later milestones with explicit review/provenance rules.
