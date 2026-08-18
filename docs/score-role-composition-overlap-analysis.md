# Score role composition overlap analysis

Issue #232 requires multiple explicitly selected score tracks to contribute to one Rocksmith Bass, Lead, or Rhythm arrangement without silently losing conflicting musical material. Before any note-stream merge exists, the project needs a deterministic way to expose where those selected tracks intersect.

`score_role_composition_overlap.py` adds a read-only overlap report bound to the exact score SHA-256 and format already carried by the human-confirmed `ScoreRoleCompositionPlan`. For each arrangement role it compares notes only across different selected source tracks and preserves both source track indexes and event indexes for every reported overlap.

The report distinguishes three mechanical facts:

- `exact_duplicate`: same onset, duration, MIDI pitch, and available string/fret identity;
- `coincident_start`: notes begin together but are not exact duplicates;
- `duration_overlap`: one selected-track note sustains into material from another selected track.

These categories are evidence, not musical decisions. An exact duplicate is not automatically deleted. A coincident start is not automatically turned into a chord. A duration overlap is not automatically shortened, split, prioritized, or rejected. The ordered composition plan also remains intent only; this analysis grants no new source, timing, fingering, chord, technique, tone, validation, or export authority.

The analyzer fails closed when a selected track is absent from the supplied normalized score tracks or when duplicate source-track identities make provenance ambiguous. Notes within a single source track are intentionally outside this layer because this slice is specifically about cross-track composition pressure.

This is the next bounded prerequisite for safe multi-track fan-out. A later slice can bind this overlap evidence to project-local normalized score data and require explicit review/section policy before any composed arrangement is published.

Safety boundaries remain unchanged: no live Rocksmith installation or NoCableLauncher state is modified; no commercial audio/DLC, private CFSM exports, Ubisoft-derived content, PSARC packages, or generated private project data are committed; uncertain musical decisions remain human-controlled.
