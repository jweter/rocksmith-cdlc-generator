# Review queue summary

A Product Reality run with a real multi-track GP5 showed that a full-song import can produce more than a thousand review-required events even when many share the same source-trust condition. Presenting those events only as a flat next/previous queue makes a systemic condition look like thousands of independent musical decisions.

`review_queue_summary.py` adds a read-only aggregate over the existing preview review queue. It reports total review-required events, unresolved-position totals, and deterministic buckets by arrangement role and source trust class.

This is deliberately informational. The summary does not accept source trust, resolve fingering, suppress queue items, change timing, or mutate imported artifacts. It is the first bounded step for issue #268: future Song Workspace work can use the aggregate to present review pressure clearly and add provenance-bearing track/region acceptance without weakening per-event exception review.

Safety boundaries remain unchanged: uncertain source, timing, fingering, chord, technique, and tone decisions remain human-controlled; no live Rocksmith or NoCableLauncher state is touched; no commercial audio/DLC, private CFSM exports, generated private project data, or Ubisoft-derived content is committed.
