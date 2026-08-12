# ADR-073: Read-only Song Preview musical context

## Status

Accepted.

## Context

Milestone 11 requires the synchronized Song Workspace to show beat position, local BPM, and time-signature context while the playhead moves. Existing preview consumers expose trusted arrangement notes, viewport lanes, review navigation, click scheduling, loop ranges, and playhead note state, but the GUI still needs a deterministic ruler-level musical context contract.

## Decision

Add `PreviewMusicalContext`, derived exclusively from `SongPreviewSnapshot` and a non-negative playhead timestamp.

The projection exposes:

- previous and next canonical beat indices/timestamps;
- normalized phase between bracketing beats;
- local BPM calculated from the actual bracketing beat interval;
- the latest source tempo event at or before the playhead;
- the latest source time-signature event at or before the playhead.

Beat-grid BPM and imported tempo metadata remain distinct on purpose. The former describes the canonical rendered timing interval; the latter preserves source notation metadata for display and diagnostics.

The reader fails closed on non-monotonic beat, tempo-event, or time-signature timing instead of sorting or repairing authoritative inputs silently.

## Boundaries

This projection is read-only. It does not move beats, infer downbeats, rewrite tempo events, edit measures, mutate the trusted snapshot, control audio devices, package DLC, or modify the live Rocksmith installation or NoCableLauncher.

## Consequences

A future Song Workspace can render a moving beat ruler and local BPM/time-signature display against one deterministic contract. Timing correction remains a separate, provenance-aware human-review workflow.