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

CLI (`cdlc-score-composition`) and Song Workspace UI wiring for selecting, resolving
overlaps for, and composing this per-role note stream have since landed. What remains is
the downstream reconciliation/authoring/export consumer: today, `score_fanout.py`'s
Bass import and `shared_guitar.py`'s Lead/Rhythm chart build still each fail closed
(`_reject_unconsumed_multi_track_bass_composition` /
`_reject_unconsumed_multi_track_composition`) rather than silently building from only the
confirmed primary track whenever a human has composed more than one. No commercial
audio/DLC, private CFSM exports, Ubisoft-derived content, PSARC packages, or generated
private project data belong in this module or its tests.

## Design sketch for downstream single-track consumption (not yet implemented)

This section records a candidate design for retiring the two fail-closed guards above by
actually consuming `RoleCompositionFanoutRecord.notes`, evaluated but **not implemented**
during a 2026-08-19 investigation session. It is written down so a future dedicated run
does not have to re-derive it, and so it does not repeat the one concrete correctness gap
that investigation found. This is analysis, not an authorized or in-progress change.

### Candidate strategy: materialize the composed stream as an ordinary single-track fan-out output

Every consumer downstream of fan-out (`alignment_for_role`, `reconcile_bass_sources`,
`apply_reviewed_positions`/`apply_reviewed_event_timing_to_source`/
`apply_reviewed_techniques_to_source`/`reviewed_chord_groups`, `build_guitar_authoring_chart`)
ultimately reads one `ImportedSource` with exactly one `SourceTrack` and matches it against
the human-confirmed primary track's `source_track_index` — never against the raw score
file's track list directly. Nothing downstream of fan-out re-derives "how many original
score tracks contributed to this."

That means a composed multi-track note stream could be written out as one ordinary
single-track `ImportedSource` — instrument-tagged for the target role, `source_track_index`
set to the role's confirmed *primary* track index (`ScoreRoleCompositionSelection.
source_track_indices[0]`, which `validate_score_role_composition` already guarantees
equals `mapping.source_track_index`), with `tracks[0].notes` set to
`[item.note for item in record.notes]` (already start-time sorted by `compose_role_notes`,
satisfying `SourceTrack.notes_are_ordered`) — and every existing single-track consumer
listed above would accept it completely unchanged. Score-level fields (`tempo_events`,
`time_signatures`, `beat_times_seconds`, `ticks_per_beat`, `tuning_midi`) should be taken
from the already-persisted per-track imports (`RoleCompositionFanoutRecord.track_outputs`)
and explicitly cross-checked for agreement across every contributing track before trusting
one of them, rather than assuming they must match because it is "the same score file" —
fail closed on disagreement instead of silently picking one.

`score_fanout.py`'s Bass import and `shared_guitar.py`'s
`_build_project_shared_guitar_chart_locked` would each, immediately before their current
single-track import call, check for a *current* (`load_current_score_role_composition_fanout`
— or a lock-safe equivalent, see below) `RoleCompositionFanoutRecord` whose
`source_track_indices` matches the role's live composition selection, and materialize that
instead of importing only the primary track. A composition selecting more than one track
with no matching composed record yet (`multi_track_pending`) would keep failing closed with
actionable guidance, exactly as today — the guard is not weakened, only given a second,
successful outcome when the human has already done the compose-with-overlap-decisions work.

### Two concrete traps found while evaluating this, that any implementation must close

1. **Lock re-entrancy.** `load_current_score_role_composition_fanout` opens its own
   `score_mapping_transaction`, which is not re-entrant (already noted in this module's
   `_current_composition_plan_locked`). Bass/Lead-Rhythm fan-out already holds that lock
   when it would need this check, so it must call a lock-assuming variant of the loader
   (e.g. a small `..._locked(project)` wrapper around the existing private
   `_load_current_locked`) rather than the public transaction-opening one, or it will
   deadlock.
2. **Bass derivative invalidation binds to `track_index` alone, not fan-out content.**
   `score_fanout.py::_invalidate_stale_bass_derivatives` treats `charts/bass_reconciled.json`
   / `review/source_disagreements.json` as still current whenever
   `reconciliation.source_sha256 == score.source_sha256 and reconciliation.track_index ==
   bass_mapping.source_track_index`. Adding a second or third track to an existing
   composition leaves the confirmed *primary* track index unchanged, so this check would
   incorrectly treat a reconciliation built from the old, smaller composed (or single-track)
   note stream as still matching the new one — a silent stale-derivative bug, the exact
   pattern issue #193 tracks as recurring. Consuming the composed stream for Bass therefore
   requires first rebinding this (and `ReconciledBassChart`/`SourceDisagreementReport`
   generally) to the fan-out output's own content identity, not `(score_sha256,
   track_index)` alone.

A non-exhaustive audit checklist of every other `source_track_index ==` / `track_index ==`
comparison to individually re-verify before trusting this design, found via
`grep -rn "track_index\s*=="`: `reviewed_positions.py`, `reviewed_event_timing.py`,
`reviewed_techniques.py`, `reviewed_chords.py`, `guitar_authoring.py`, `alignment.py`,
`score_preview.py`, `chord_identity_ui.py`, `score_mapping_review.py`,
`score_role_composition_workspace_status.py`. Most of these key off the *current* fan-out
output's own event ordering/content hash (safe under this design), but each needs the same
scrutiny applied to trap 2 above before this is implemented, not assumed safe by analogy.

Bass and Lead/Rhythm should land as separate PRs, mirroring how the two fail-closed guards
themselves were split (Lead/Rhythm, then Bass).
