# ADR-067: Read-only Song Preview review queue

## Status

Accepted.

## Context

Milestone 11 requires the Song Preview & Timing Editor to make the next item needing human attention obvious and to support next/previous review navigation. PR #80 established a trusted read-only Song Preview snapshot, and PR #81 added a viewport-oriented timeline projection. The next GUI-facing layer needs a deterministic way to surface review-required arrangement events without editing charts or inventing confidence.

## Decision

Add a read-only `PreviewReviewQueue` projection derived exclusively from `SongPreviewSnapshot`.

The queue:

- includes only notes whose normalized source event already has `review_required=true`;
- retains arrangement, event index, onset/duration, pitch, string/fret, techniques, confidence, and trust class;
- assigns a stable `instrument:event_index` review identifier within the trusted snapshot;
- sorts primarily by song position so navigation follows playback order;
- at equal onsets, surfaces lower-confidence items first, then uses deterministic Lead/Rhythm/Bass ordering and event index as tie-breakers;
- copies mutable values such as technique lists so UI-side queue state cannot mutate the trusted snapshot.

## Boundaries

This layer does not mark reviews complete, alter timing, change note/fret mappings, write review artifacts, mutate the MusicXML manifest, package DLC, or touch the live Rocksmith installation or NoCableLauncher. Human decisions remain explicit future actions backed by separate provenance-aware review artifacts.

## Consequences

A future Song Workspace can implement next/previous review navigation immediately against a deterministic engine contract. Review prioritization remains transparent and reproducible, while all authoritative musical data stays unchanged until an explicit editing/review workflow is introduced.
