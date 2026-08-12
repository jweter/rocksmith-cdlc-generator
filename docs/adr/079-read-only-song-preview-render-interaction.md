# ADR-079: Read-only Song Preview render interaction

## Status

Accepted.

## Context

The Song Preview engine can now produce provenance-bound normalized render geometry, locate arrangement events near an absolute timestamp, and hand unambiguous selections to the event inspector. A future desktop timeline still needs a framework-neutral bridge from a normalized horizontal interaction coordinate back to song time without placing timing interpretation or implicit event-selection policy inside Qt widgets.

## Decision

Add `PreviewTimelineInteractionState`, derived from the trusted `SongPreviewSnapshot`, a provenance-bound `PreviewTimelineRenderGeometry`, an arrangement role, a normalized x fraction, and an explicit caller-provided event-selection tolerance.

The interaction projection:

- verifies render geometry source filename and SHA-256 against the supplied trusted snapshot;
- requires a finite x fraction in the closed 0..1 viewport range;
- requires a finite, non-negative explicit tolerance;
- revalidates finite viewport endpoints and a consistent positive render duration before coordinate conversion;
- converts the normalized coordinate deterministically to an absolute song timestamp;
- rebuilds the event locator from the trusted snapshot rather than trusting rendered event rectangles.

## Boundaries

This layer is read-only. It does not move the playhead, control audio hardware, change timing, select among ambiguous musical events, edit notes or techniques, mutate manifests/imported artifacts, package DLC, or modify the live Rocksmith installation or NoCableLauncher. The caller owns input-modality/zoom-specific tolerance policy, and ambiguous candidates remain explicit human-visible choices downstream.

## Consequences

A future PySide6/Qt timeline can translate mouse or touch coordinates into trusted Song Preview interactions through one deterministic, testable contract while keeping UI code free of authoritative timing mutation logic.
