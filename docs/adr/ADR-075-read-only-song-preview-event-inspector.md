# ADR-075: Read-only Song Preview event inspector

## Status

Accepted.

## Context

The Song Preview engine now exposes a trusted snapshot, viewport lanes, playhead state, fretboard state, review navigation, musical context, and a composed workspace state. A desktop Song Workspace also needs a deterministic contract for clicking one arrangement event and showing its detail panel without reading or mutating authoritative source models directly.

## Decision

Add `PreviewEventSelectionState`, derived only from `SongPreviewSnapshot`, an arrangement role, and a stable full-arrangement event index.

The projection exposes:

- a stable `instrument:event_index` selection identifier;
- source filename and SHA-256 provenance inherited from the trusted snapshot;
- arrangement part identity, name, and tuning;
- a deep-copied selected normalized event;
- deep-copied chronological previous/next events for inspector navigation;
- the matching review identifier only when the selected event already requires human review.

Neighbor order is deterministic by onset and event index. Duplicate arrangement roles or event indices fail closed rather than producing an ambiguous selection.

## Boundaries

This layer is read-only. It does not change note timing, pitch, string/fret placement, techniques, confidence, review state, manifests, imported artifacts, or source provenance. It does not control audio hardware, package DLC, or modify the live Rocksmith installation or NoCableLauncher. Uncertain musical decisions remain explicit human-review actions.

## Consequences

A future GUI can implement note-click selection and a detail inspector against one deterministic view-model contract while preserving the current separation between trusted imported data and later provenance-aware editing artifacts.
