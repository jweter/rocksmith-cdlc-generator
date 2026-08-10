# ADR-013: Symbolic-to-audio beat-grid alignment

## Status

Accepted

## Context

Imported MIDI, Guitar Pro, and MusicXML sources describe musical time, but their timestamps usually do not match the exact recording used for Rocksmith authoring. A fixed offset is insufficient for live tempo drift or imperfect source tempo maps. Unconstrained dynamic time warping could reorder events or hide a bad symbolic source.

## Decision

Align imported symbolic time to `analysis/tempo_map.json` using a monotonic piecewise-linear beat mapping.

The first implementation:
- derives a symbolic beat grid from imported tempo events;
- estimates a plausible audio start beat from local beat-interval similarity unless explicitly overridden;
- pairs symbolic and analyzed audio beats in order;
- places warp anchors at a configurable beat stride;
- interpolates monotonically between anchors;
- records global offset, residual statistics, per-region confidence, and warnings in `analysis/alignment.json`;
- exposes low-confidence alignment rather than silently promoting symbolic notes to verified status.

The alignment layer does not change source notes and does not mark them `symbolic_verified`. Verification belongs to the later reconciliation stage where pitch/onset evidence can also be considered.

## Consequences

This approach handles recording offsets and gradual tempo drift while preserving event order. It is deterministic, lightweight, and testable without a GPU. It cannot yet resolve complex repeat/navigation playback order or missing/extra measures automatically; those conditions remain warnings/manual alignment concerns until a later structural alignment pass is added.
