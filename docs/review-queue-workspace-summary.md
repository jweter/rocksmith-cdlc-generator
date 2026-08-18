# Song Workspace review queue summary

Issue #268 requires review pressure to be understandable before a user is sent through individual events. The existing `ReviewQueueSummary` model already classifies the current queue by arrangement/trust bucket and by overlapping review reasons. This slice surfaces that read model in the final Arrangement Preview.

The panel reports the total review-required event count, unresolved-position count, overlapping reason counts, and per-arrangement/source-trust counts. Reason counts intentionally overlap: for example, one event can still require event review while also carrying `symbolic_unverified` trust and a `tie` marker.

This is a read-only UI integration. It does not remove queue items, accept source trust, accept ties or techniques, resolve positions, alter timing, change score/fan-out bytes, or modify any downstream authoring/package authority. Existing human review gates remain authoritative.

No live Rocksmith installation or NoCableLauncher state is touched, and no commercial audio/tabs, PSARCs, private CFSM exports, Ubisoft-derived content, or generated private project data are committed.
