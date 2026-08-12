# ADR-078: Read-only Song Preview render geometry

## Status

Accepted.

## Context

The Song Preview engine now exposes trusted timeline windows, synchronized workspace state, event location, and event inspection. A future desktop timeline still needs a framework-neutral way to convert canonical song time into drawable positions without teaching Qt widgets how to interpret or mutate authoritative preview models.

## Decision

Add `PreviewTimelineRenderGeometry`, derived directly from one trusted `SongPreviewSnapshot` and an explicit non-zero time viewport.

The projection exposes:

- source filename and SHA-256 provenance;
- viewport start, end, and duration;
- canonical beat markers with stable full-song beat indices and normalized `0..1` horizontal positions;
- arrangement lanes with stable `instrument:event_index` selection identifiers;
- normalized event rectangle start/end positions;
- clipped render bounds for notes crossing viewport edges;
- a deep-copied original normalized event whose authoritative timing remains unchanged;
- arrangement tuning and part labels for GUI rendering.

Event rectangles use half-open viewport semantics: an event beginning exactly at the viewport end is not emitted as a zero-width rectangle. Canonical beats may still appear at the right boundary as ruler markers.

The render boundary fails closed on zero-width/reversed viewports, non-monotonic canonical beat grids, duplicate arrangement roles, or duplicate event indices.

## Boundaries

This layer is read-only and UI-framework neutral. It does not edit timing, notes, techniques, string/fret placement, confidence, review state, manifests, or imported artifacts. It does not access audio hardware, package DLC, or modify the live Rocksmith installation or NoCableLauncher. It contains no commercial audio/DLC or Ubisoft-derived content.

## Consequences

A future PySide6/Qt timeline can draw beats and note rectangles using simple normalized coordinates while stable source identifiers and review metadata remain tied to the trusted Song Preview data model. Pixel scaling, zoom gestures, colors, and interaction policy remain GUI concerns rather than authoritative timing logic.
