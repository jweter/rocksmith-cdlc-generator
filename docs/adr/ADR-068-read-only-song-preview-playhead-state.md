# ADR-068: Read-only Song Preview playhead state

## Status

Accepted.

## Context

Milestone 11 requires synchronized playback, a moving playhead, arrangement overlays, and later a virtual fretboard. PR #80 established the trusted Song Preview snapshot, PR #81 added viewport timeline projection, and PR #82 added deterministic review navigation. The next GUI-facing consumer needs a small, deterministic answer to: what is active now, what comes next, and which beats bracket the current playback position?

## Decision

Add a separate read-only `song_preview_playhead` projection derived exclusively from `SongPreviewSnapshot`.

For a non-negative playback position it returns:

- the previous beat at or before the playhead;
- the next beat strictly after the playhead;
- one lane per arrangement with its tuning;
- every note active at the position using half-open intervals (`start <= position < end`);
- the earliest upcoming note for each arrangement;
- copied note/tuning values so GUI-side state cannot mutate the trusted snapshot.

Selection is deterministic even if a caller constructs a snapshot whose beat or note arrays are not already sorted.

## Boundaries

This projection does not seek or play audio, edit timing, alter notes or fret mappings, mark reviews complete, write review artifacts, package DLC, inspect or modify the live Rocksmith installation, or interact with NoCableLauncher. It consumes trusted cached data only.

## Consequences

A future Song Workspace can update a moving playhead, note overlays, and virtual-fretboard previews without embedding chart-selection logic in the GUI. Authoritative timing and musical data remain unchanged until separate provenance-aware editing workflows are implemented behind explicit human review gates.
