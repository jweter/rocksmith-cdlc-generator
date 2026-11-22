# #796 slice 36 — explicit guitar tuning and physical note proof

## Concrete defect (ERR-2026-022)

The Song Workspace's preview projected a source `string_index` and `fret` to a physical fretboard marker without proving the recorded `midi` equals `tuning_midi[string_index] + fret`. The live Arrangement Preview canvas did the same. A song with E4 (MIDI 64) erroneously marked as open low E2 (string 0, fret 0) appeared plausible and passed old preview/workspace tests. Missing tuning was already guarded in one path, but wrong string counts and mismatched positions were not, so inconsistent source notation could look authoritative.

## Production implementation

Both the actual live Arrangement Preview canvas and the view-model path `build_preview_workspace_state -> build_preview_fretboard_state` now consume the same fail-closed functions:
- `explicit_tuning_is_valid(role, tuning)`: present only when the source declares valid integer MIDI open-string pitches and a supported string count (Bass 4–6, preview guitar 6–8); no inferred tuning.
- `note_matches_explicit_tuning(...)`: reject absent/negative/out-of-range string/fret, fret above this preview's visible 24-fret bound, and every source note for which the declared open string plus fret is not exactly the recorded MIDI note. No guessing another string/fret.
- Bad physical facts are **unmapped** in the shared preview state, preserving event indices for review, and omitted from the canvas rather than displayed as a playing position. Invalid tuning cannot draw a complete-looking fretboard. Other arrangement roles and the original audio/beat clock remain unchanged.

This is a conservative *physical feasibility* check. It does NOT prove source tuning was independently confirmed by playing/listening, that imported notation or capo convention is correct, or that two-bar phase, private Bass/Lead/Rhythm note truth and gameplay are resolved. The six-string guitar authoring/export path already refuses missing tuning; this update closes the live preview discrepancy and adds a source-fact regression to the integrated preview workspace.

## Mature reference behavior

Read `raynebc/editor-on-fire@27efe8a85ec8568caaa3ca34ab2d3ea326236725/src/tuning.h` (played-note pitch lookup via defined string tuning and fret) and `src/mix.c` (track tuning/default lookup, fret, and capo compose audible pitch). EOF allows an explicit user preference to ignore tuning/capo for selected lookup behaviors; this product intentionally does **not** apply a default/ignored tuning for physical authority, because the source identity and review boundaries require exactly declared tuning to prevent silent musical misinformation. No upstream source code is copied.

## Pre-PR verification and acceptance

Original synthetic six-string standard/down-tuned Guitar, Bass, absent/malformed tuning, wrong-string index, late/out-of-range fret, wrong MIDI and mixed correct/incorrect notes. Tests exercise both direct physical projection and the actual GUI canvas, and the real Song Workspace view-model. A legacy workspace fixture incorrectly placed E4 on open low E2; repaired the synthetic fixture rather than weakening the new invariant. The timing, chart generation and export paths retain their current independent gates.

Canonical tracker #796 slice **35** was verified merged as PR #816 at `54e8fc08391d4bf4ebf17a6e20047f3301588a3c` from exact reviewed head `ad1b5c4b66b2cf92a13e78d9ffba88f989c104b2`; its checked item SHA-256 is independently bound in `engineering/rocksmith-slice-dependencies.json` and fail-closed dispatcher tests now require 24 receipts. **Slice 36 remains unchecked** pending exact-head Python/Windows Desktop/PSARC/Golden/Security/Control/Execution Director/queue CI, fresh independent review, verified merge, and separate receipt reconciliation.
