# ADR-069: Read-only Song Preview fretboard state

## Status

Accepted.

## Context

Milestone 11 requires a synchronized virtual fretboard that reflects each arrangement's actual tuning and makes active/upcoming physical positions visible. PR #83 established a read-only playhead projection with active and next events per arrangement. The next engine contract should expose only physical positions already present in trusted preview data without inventing alternate mappings or introducing correction writes.

## Decision

Add a read-only `PreviewFretboardState` projection derived from `PreviewPlayheadState`.

The projection:

- includes only lanes with explicit tuning data;
- exposes active and next-event string/fret markers when both values are present;
- preserves event index, pitch, confidence, trust class, and review-required state;
- surfaces unmapped event indices explicitly when string/fret data is absent instead of inferring a position;
- copies tuning and marker data so GUI-side state cannot mutate trusted playhead or source data.

## Boundaries

This layer does not generate alternate positions, correct fret mapping, edit note timing, mark review items complete, write review artifacts, package DLC, or touch the live Rocksmith installation or NoCableLauncher. Human mapping decisions remain explicit future review actions.

## Consequences

A future Qt fretboard widget can render trusted active/upcoming positions immediately while clearly preserving unresolved mappings for human review. Alternate-position generation and correction can be added later behind provenance-aware review artifacts rather than being silently inferred in the display layer.
