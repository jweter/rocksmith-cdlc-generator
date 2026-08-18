# Score role composition fan-out review

Issue #232 requires fan-out and downstream staleness/invalidation to bind to the full
selected source-track set for a role, not one track ID. The composition contract, the
persisted plan, the cross-track overlap analysis, the human overlap-decision contract,
and the pure in-memory `compose_role_notes` merge already existed. This slice adds the
first module that actually imports every currently selected source track and persists
the resulting composed note stream as a provenance-bound project artifact.

`score_role_composition_fanout_review.py` provides:

- `compose_and_persist_score_role_composition_fanout` — for one role, imports (or
  re-imports) every source track currently selected in the persisted
  `ScoreRoleCompositionPlan`, merges them with `compose_role_notes` using the supplied
  human overlap decisions, and atomically persists a `RoleCompositionFanoutRecord` at
  `review/score_role_composition_fanout.json`. Per-track imports are written
  project-locally under `sources/imported/composition/<role>-track<index>-<sha12>.json`.
- `load_current_score_role_composition_fanout` — reloads the persisted layer and fails
  closed unless the registered score, the exact ordered persisted composition track set
  for every recorded role, and every recorded per-track output's current bytes all still
  match. A stale record is not silently kept partially current; the whole record for
  that role is rejected.

## Fail-closed staleness boundary

Unlike a single-track fan-out entry bound to one track ID, `RoleCompositionFanoutRecord`
binds staleness to the complete ordered `source_track_indices` list for a role:

- If the persisted composition plan's selection for a role changes at all (a track is
  added, removed, or reordered), the previously composed record for that role fails
  closed on the next load rather than remaining authoritative for a track set that no
  longer matches human intent.
- If any one selected track's re-imported bytes change, the whole record for that role
  fails closed, mirroring `source_track_trust_review.py`'s provenance-binding pattern.
- Composition itself still fails closed for any unresolved cross-track overlap, an
  unknown role, a stale/mismatched overlap decision plan, or a missing selected source
  track, via the existing `compose_role_notes` contract.
- A stale or corrupt prior review layer is discarded wholesale on the next explicit
  recompose rather than permanently blocking a new explicit human-directed rebuild;
  the new record is fully revalidated against current score/plan/track content first.
- Recomposing one role's record leaves every other role's currently valid record
  untouched.

## What this does not do

This module does not accept/change source rights, primary mapping confirmation, timing,
fingering, technique, chord, or tone decisions, does not persist the human overlap
decision plan itself (that remains a caller-supplied input, matching
`compose_role_notes`), and does not write Rocksmith XML, package CDLC, modify the live
Rocksmith installation, or interact with NoCableLauncher.

## Next integration step

A later bounded slice can wire this composed, persisted per-role note stream into a CLI
command and/or Song Workspace UI for selecting/reviewing composition, and eventually
into downstream reconciliation/authoring/export once composed multi-track material is
ready to carry that authority. No commercial audio/DLC, private CFSM exports,
Ubisoft-derived content, PSARC packages, or generated private project data belong in
this module or its tests.
