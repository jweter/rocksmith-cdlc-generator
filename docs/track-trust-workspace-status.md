# Track source-trust workspace status

Issue #268 requires whole-track source acceptance to be explicit, provenance-bound, and understandable in Song Workspace without weakening independent human review.

`track_trust_workspace_status.py` adds the read-only control model that the desktop workspace can render before wiring the acceptance button itself. For each current human-confirmed Bass, Lead, or Rhythm fan-out track it reports:

- source track identity and note count;
- whether whole-track acceptance is `unreviewed`, `current`, or `stale`;
- the exact accepted scope, `imported_note_identity_and_positions`;
- whether the current fan-out is eligible for explicit acceptance;
- actionable blocker counts for unresolved positions, position/pitch conflicts, non-symbolic source facts, missing tuning, or empty tracks.

A stale or malformed prior `review/source_track_trust.json` is surfaced as stale rather than silently treated as current authority. The current fan-out is still inspected independently so the UI can explain when the explicit reacceptance path added by #275 is safe to offer.

This model grants no musical authority. It does not record acceptance, mutate fan-out bytes, change note trust, clear per-event review flags, infer positions, accept ties or techniques, alter timing, confirm chords, approve source rights, choose tones, validate arrangements, package CDLC, modify the live Rocksmith installation, or interact with NoCableLauncher.

The next bounded integration step is to render this model in Arrangement Preview and call the existing explicit `record_track_source_trust_acceptance()` operation only from a deliberate user action. Independent review reasons must remain visible after that action.
