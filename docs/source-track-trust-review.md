# Track-level imported source trust review

Product Reality testing with a real full-song GP5 exposed a scale failure in the review workflow: hundreds of concrete imported score events can carry the same `symbolic_unverified` source-trust state, making a coherent track-level decision look like hundreds of unrelated note clicks.

The provenance-bearing backend contract reviews one exact imported Bass, Lead, or Rhythm source track as a unit. The review artifact is stored at `review/source_track_trust.json` and is bound to:

- the current registered complete-score SHA-256 and format;
- the current human-confirmed arrangement-role mapping and source-track index;
- the exact current score fan-out manifest path and SHA-256;
- the exact project-local fan-out output path and SHA-256;
- the source track name and note count.

Recording acceptance validates every source note covered by the scope. The track must have explicit tuning, every note must already carry a concrete string/fret position, and each position must reproduce the imported MIDI pitch. Missing or pitch-inconsistent positions fail closed rather than being invented.

The accepted scope is deliberately narrow: `imported_note_identity_and_positions`. It records that a human accepted the exact imported symbolic note/position facts for that track snapshot. It does **not** accept or clear independent timing, technique, tie, chord-identity, chord-fingering, validation, source-rights, tone, or package-readiness decisions.

The Song Workspace preview read model may consume a current acceptance by projecting the copied track's symbolic trust class to `user_confirmed`. This projection is allowed only when the supplied source model exactly matches the accepted current fan-out content. Persisted fan-out bytes remain unchanged, and per-event `review_required` flags, techniques, positions, timing, chord facts, and durations are preserved. An ambiguous tie or any other independent review condition therefore remains individually reviewable even after whole-track source acceptance.

Both acceptance writes and current-review loads run under the shared score-mapping transaction. Any registered-score, mapping, fan-out-manifest, or fan-out-output drift makes the old review stale and prevents it from granting authority. A stale or malformed prior review does not, however, permanently block a later explicit human decision: once the currently selected track has independently passed the full current score/mapping/fan-out/tuning/position/pitch validation, recording a new acceptance discards the stale layer wholesale and writes a fresh exact-snapshot review. This deliberately favors loss of stale review evidence over carrying any old authority forward. Read-only loads continue to fail closed until that explicit replacement occurs.

Preview projection also rejects a caller-supplied source model that differs from the accepted fan-out snapshot. This prevents a track-level decision from silently following regenerated, remapped, or locally altered source data.

This is a read-model integration only. It does not rewrite imported events or manufacture authority in persisted artifacts. Downstream authoring/export gates continue to decide explicitly which human evidence they require.

No commercial media, tabs, generated private project data, Ubisoft-derived content, or package artifacts are added to Git. This review layer cannot modify the live Rocksmith installation or NoCableLauncher.
