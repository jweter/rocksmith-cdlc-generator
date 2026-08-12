# ADR-072: Read-only Song Preview review navigation

## Status

Accepted.

## Context

Milestone 11 requires next/previous review navigation so the Song Workspace can move directly between events that already require human attention. ADR-067 established a deterministic read-only review queue, but callers still need a stable contract for navigating that queue by selected review item or current playhead position.

## Decision

Add pure read-only navigation helpers over `PreviewReviewQueue`.

The navigation layer:

- selects a review item by stable `review_id`;
- exposes copied previous/current/next items without wrapping at queue boundaries;
- can select the first review item at or after a non-negative playhead position;
- selects the final queue item when the playhead is beyond all remaining review items so backward navigation remains available;
- rejects duplicate review identifiers and position-navigation queues that are not ordered by song onset;
- deep-copies returned review data so GUI state cannot mutate the trusted queue.

## Boundaries

This layer does not mark reviews complete, edit timing, change notes or string/fret mappings, write review artifacts, mutate source manifests, control audio hardware, package DLC, or touch the live Rocksmith installation or NoCableLauncher.

## Consequences

The future Song Workspace can implement deterministic next/previous review buttons and playhead-to-review jumps without introducing an editing path. Human decisions remain explicit future actions backed by separate provenance-aware review artifacts.
