# Review queue summary

A Product Reality run with a real multi-track GP5 showed that a full-song import can produce more than a thousand review-required events. Presenting those events only as a flat next/previous queue makes a systemic condition look like thousands of independent musical decisions.

`review_queue_summary.py` adds a read-only aggregate over the existing preview review queue. It reports total review-required events, unresolved-position totals, deterministic buckets by arrangement role and source trust class, and overlapping reason counts for:

- the explicit source-level `review_required` condition that put the event in the queue;
- `symbolic_unverified` source trust;
- missing string/fret positions;
- imported `tie` technique markers.

The reason counts are deliberately overlapping. A queue item may be both `symbolic_unverified` and a `tie`, for example. Source trust therefore must not be treated as the sole cause of queue membership merely because it is visible on the same event. This distinction is required before issue #268 can safely use provenance-bound whole-track acceptance to remove only redundant trust review while preserving independent event, technique, timing, fingering, chord, and validation review reasons.

This is deliberately informational. The summary does not accept source trust, resolve fingering, suppress queue items, change timing, or mutate imported artifacts. The underlying queue remains unchanged.

Safety boundaries remain unchanged: uncertain source, timing, fingering, chord, technique, and tone decisions remain human-controlled; no live Rocksmith or NoCableLauncher state is touched; no commercial audio/DLC, private CFSM exports, generated private project data, or Ubisoft-derived content is committed.
