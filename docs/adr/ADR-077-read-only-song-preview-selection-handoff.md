# ADR-077: Read-only Song Preview selection handoff

## Status

Accepted.

## Context

The Song Preview engine can locate timeline events near a timestamp and inspect one stable event in detail. A GUI still needs a deterministic bridge between those two contracts without silently resolving overlapping notes, trusting mutable locator payloads as authoritative source data, or resolving a stale locator against a different song after the workspace reloads.

## Decision

Add `PreviewSelectionHandoff`, derived from the trusted `SongPreviewSnapshot` and a `PreviewEventLocatorState`.

The locator carries the trusted snapshot source filename and SHA-256. The handoff must verify both values against the supplied snapshot before resolving any event identifier.

The handoff:

- automatically resolves a locator only when exactly one candidate exists;
- preserves multiple candidates as `requires_choice=True` until the caller supplies an explicit candidate `selection_id`;
- rejects selections that were not returned by the locator;
- rejects locator state whose source filename or SHA-256 does not match the supplied snapshot;
- validates candidate identity and duplicate IDs before resolution;
- rebuilds final inspector state from the trusted snapshot by stable instrument/event index rather than trusting the locator's copied event payload;
- leaves an empty locator unselected.

## Boundaries

This layer is read-only. It does not change timing, pitch, techniques, string/fret placement, confidence, review state, manifests, imported artifacts, or source provenance. It does not control audio hardware, package DLC, or modify the live Rocksmith installation or NoCableLauncher. Overlapping musical events remain explicit human-visible choices.

## Consequences

A future Song Workspace can safely connect timeline clicks to the event detail panel while keeping ambiguous musical selections under human control, preventing stale cross-song selection state, and keeping the trusted snapshot authoritative.
