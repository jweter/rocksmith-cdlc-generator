# ADR-076: Read-only Song Preview event locator

## Status

Accepted.

## Context

The Song Preview engine can now expose a composed workspace and inspect a selected event by stable arrangement role plus event index. A GUI timeline still needs a deterministic way to translate a clicked or seeked timestamp in one arrangement lane into one or more candidate events without reaching into authoritative source models or silently choosing among musically ambiguous overlaps.

## Decision

Add `PreviewEventLocatorState`, derived only from `SongPreviewSnapshot`, an arrangement role, a non-negative timestamp, and an explicit non-negative tolerance.

The locator:

- returns all events whose half-open duration contains the timestamp as `overlap` candidates;
- if nothing overlaps, returns every event whose nearest boundary is within the explicit tolerance as `nearby` candidates;
- returns `none` when no event qualifies;
- preserves ambiguity as multiple candidates rather than guessing which note/chord member the user intended;
- orders candidates deterministically by distance, onset, and stable event index;
- returns deep-copied event values suitable for GUI selection handoff;
- fails closed on missing/duplicate arrangement roles or duplicate event indices.

## Boundaries

This layer is read-only. It does not modify timing, pitch, string/fret placement, techniques, review state, manifests, imported artifacts, or source provenance. It does not control audio devices, package DLC, touch the live Rocksmith installation, or modify NoCableLauncher. Ambiguous musical selections remain explicit user choices.

## Consequences

A future Song Workspace can convert timeline clicks into stable selection candidates and then hand the chosen `instrument:event_index` to the existing event inspector. Vertical lane/fretboard geometry can refine ambiguous candidates later without weakening provenance or human-review gates.
