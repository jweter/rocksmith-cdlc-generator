# Track-level imported source trust review

Product Reality testing with a real full-song GP5 exposed a scale failure in the review workflow: hundreds of concrete imported score events can carry the same `symbolic_unverified` source-trust state, making a coherent track-level decision look like hundreds of unrelated note clicks.

This slice adds the provenance-bearing backend contract for reviewing one exact imported Bass, Lead, or Rhythm source track as a unit. The review artifact is stored at `review/source_track_trust.json` and is bound to:

- the current registered complete-score SHA-256 and format;
- the current human-confirmed arrangement-role mapping and source-track index;
- the exact current score fan-out manifest path and SHA-256;
- the exact project-local fan-out output path and SHA-256;
- the source track name and note count.

Recording acceptance validates every source note covered by the scope. The track must have explicit tuning, every note must already carry a concrete string/fret position, and each position must reproduce the imported MIDI pitch. Missing or pitch-inconsistent positions fail closed rather than being invented.

The accepted scope is deliberately narrow: `imported_note_identity_and_positions`. It records that a human accepted the exact imported symbolic note/position facts for that track snapshot. It does **not** accept or clear independent timing, technique, tie, chord-identity, chord-fingering, validation, source-rights, tone, or package-readiness decisions. It does not mutate the fan-out source or change per-event `review_required` flags in this slice.

Both acceptance writes and current-review loads run under the shared score-mapping transaction. Any registered-score, mapping, fan-out-manifest, or fan-out-output drift makes the review stale. This prevents a track-level decision from silently following regenerated or remapped source data.

The next bounded integration step can consume this contract when building the Song Workspace review queue, removing only redundant source-trust pressure while leaving events with independent review reasons in the individual queue.

No commercial media, tabs, generated private project data, Ubisoft-derived content, or package artifacts are added to Git. This review layer cannot modify the live Rocksmith installation or NoCableLauncher.
