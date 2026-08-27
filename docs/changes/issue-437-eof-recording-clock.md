# Issue #437 implementation

The EOF checker now has a separate recording-clock parity layer for sparse local observations from the same score and recording.

It reports:

- first-playable-event delta;
- per-observation mapped-vs-EOF recording-time delta;
- estimated local bar displacement;
- constant-offset vs drift classification;
- median and maximum absolute timing error;
- stale score, recording, source-track, and promoted shared-timeline failures.

This remains advisory evidence and never mutates canonical chart timing automatically.
