# ADR-075: Keep Song Preview transport state deterministic and read-only

## Status
Accepted

## Context
Milestone 11 requires play/pause/seek/scrub and looping, but the current Song Preview foundation intentionally avoids audio-device control and authoritative chart/timing edits. The existing loop helper can describe a selected interval and wrap a playhead position, but a future Qt workspace still needs one explicit transport-state contract separating the position requested by the user/audio clock from the effective synchronized preview position.

## Decision
Add a small `PreviewTransportState` projection that records the requested position, effective position, optional loop range, and whether looping is enabled.

The projection applies deterministic loop wrapping only when looping is explicitly enabled. It deep-copies loop metadata and performs no audio playback, seeking, file writes, timing correction, or arrangement mutation.

## Consequences
- GUI and audio-backend code can share one deterministic loop/position contract.
- Pre-roll before a loop remains possible because the existing loop semantics leave positions before the loop start unchanged.
- Enabling loop playback without a loop range is rejected explicitly.
- Audio-device ownership, play/pause commands, playback speed, and editing remain future layers with separate boundaries.
