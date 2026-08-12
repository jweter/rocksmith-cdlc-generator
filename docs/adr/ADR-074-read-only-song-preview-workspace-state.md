# ADR-074: Read-only Song Preview workspace state

## Status

Accepted.

## Context

Milestone 11 now has separate deterministic consumers for trusted arrangement events, viewport lanes, playhead note state, virtual-fretboard markers, review navigation, loop ranges, click scheduling, and musical ruler context. A desktop Song Workspace should not need to coordinate those low-level projections independently or read authoritative source models directly.

## Decision

Add `PreviewWorkspaceState` as a read-only composition layer over the existing Song Preview consumers.

Given one trusted `SongPreviewSnapshot`, viewport bounds, and playhead position, the workspace state exposes:

- the clipped synchronized timeline viewport;
- active and upcoming arrangement events at the playhead;
- beat/tempo/time-signature musical context;
- current virtual-fretboard state;
- the total number of review-required events;
- deterministic review navigation around the current playhead when review items exist.

Each nested consumer retains its existing validation and copying behavior. Empty review queues are represented explicitly with a zero count and no navigation state rather than by raising an error.

## Boundaries

This is a view-model composition layer only. It does not edit timing, notes, techniques, string/fret mappings, review state, loop state, manifests, or imported artifacts. It does not control audio hardware, package DLC, modify the live Rocksmith installation, or interact with NoCableLauncher. Musical uncertainty remains visible for explicit human review.

## Consequences

A future PySide6/Qt Song Workspace can bind to one deterministic engine contract instead of reconstructing synchronization logic in widgets. This reduces GUI coupling while preserving the current fail-closed, read-only safety boundary before any provenance-aware editing workflow is introduced.
