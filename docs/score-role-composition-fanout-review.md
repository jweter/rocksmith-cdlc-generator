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
Bass import still fails closed (`_reject_unconsumed_multi_track_bass_composition`) rather
than silently building from only the confirmed primary track whenever a human has composed
more than one. No commercial audio/DLC, private CFSM exports, Ubisoft-derived content,
PSARC packages, or generated private project data belong in this module or its tests.

**Update (Lead/Rhythm slice landed, issue #232):** `shared_guitar.py`'s Lead/Rhythm chart
build now consumes the composed multi-track note stream for a role, retiring
`_reject_unconsumed_multi_track_composition` in favor of
`_current_composed_record_for_role` (still fails closed the same way when a role's
composition selects more than one track but no current composed fan-out record exists yet
for that exact selection). See the "Downstream consumption: Lead/Rhythm (landed)" section
below for the implemented design and what is intentionally still deferred (Bass).

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

## Downstream consumption: Lead/Rhythm (landed)

This section documents the design actually implemented for `shared_guitar.py`, following
the candidate strategy above, and what a follow-on Bass slice must still account for.

- `_current_composed_record_for_role(project, role=...)` replaces
  `_reject_unconsumed_multi_track_composition`. It still returns `None` (ordinary
  single-track path, unchanged) whenever the persisted composition plan is missing/stale/
  unreadable or selects at most one track for the role. When the role's composition
  selects more than one track, it loads the persisted fan-out layer through
  `score_role_composition_fanout_review._load_current_locked` directly rather than the
  public `load_current_score_role_composition_fanout` -- `_build_project_shared_guitar_
  chart_locked` already holds the `score_mapping_transaction` lock at this call site, and
  that lock is not re-entrant (this closes Trap 1 from the design sketch above). It fails
  closed with the same "not yet consumed" class of error whenever a matching current
  record does not exist yet.
- `_materialize_composed_guitar_source` builds the composed stream as one ordinary
  single-track `ImportedSource`, exactly per the candidate strategy: `tracks[0].notes` is
  `[item.note for item in record.notes]` (already start-time ordered), `source_track_index`
  is the confirmed primary (`record.source_track_indices[0]`), and score-level fields
  (`ticks_per_beat`, `tempo_events`, `time_signatures`, `beat_times_seconds`, and also
  `tuning_midi`) are taken from the first contributing track's persisted per-track import
  and explicitly cross-checked for exact equality against every other contributing track's
  import before being trusted -- any disagreement fails closed rather than silently
  picking one track's values. The merged single-track source is written to
  `sources/imported/composition/<role>-composed-<score_sha12>.json` and consumed exactly
  like the existing single-track fan-out output by every downstream step already in
  `_build_project_shared_guitar_chart_locked` (`apply_reviewed_positions`,
  `apply_reviewed_event_timing_to_source`, `apply_reviewed_techniques_to_source`,
  `reviewed_chord_groups`, `build_guitar_authoring_chart`) -- none of those call sites
  changed.
- `SharedGuitarDraftManifest` gained two new optional fields,
  `composed_source_track_indices` and `composed_fanout_record_sha256` (both `None`
  together for an ordinary single-track draft, both set together for a composed one).
  `load_current_shared_guitar_draft` branches on them: a single-track draft keeps the
  original `source_path == alignment.source_path` currentness check unchanged; a composed
  draft instead re-loads the *current* fan-out record for the role (via the public,
  lock-opening `load_current_score_role_composition_fanout`, since this read path is never
  called from inside an existing lock) and requires both its `source_track_indices` and a
  content fingerprint (`sha256` of the record's own JSON) to still match what the draft was
  built from -- so narrowing/reordering/recomposing the selection after a composed draft
  was built makes that draft fail closed as stale, the same way any other input drift does
  elsewhere in this pipeline.
- Trap 2 (Bass derivative invalidation binding to `(score_sha256, track_index)` alone,
  not fan-out content) does not apply to this slice: Lead/Rhythm shared-guitar chart
  building has no analogous `track_index`-only staleness check of its own to fix --
  `SharedGuitarDraftManifest` staleness was already content-hash-bound for every other
  layer, and the two new composed-specific fields extend that same pattern rather than
  introducing a `track_index`-only shortcut. Trap 2 still applies in full to the deferred
  Bass slice (`score_fanout.py::_invalidate_stale_bass_derivatives`) and must be closed
  there before Bass consumes composed multi-track output.
- Known, deliberately out-of-scope limitation carried over unchanged from
  `_load_current_locked`: it validates every persisted role's fan-out record when loaded,
  not only the role currently being built/checked. A stale/unrelated *other* role's
  composed record (e.g. Bass) can therefore cause a Lead build's composition lookup to
  raise, even though only Lead is being built. This always fails closed (never silently
  wrong), so it is left as-is rather than expanding this slice's scope; a future slice
  could narrow `_load_current_locked`/`load_current_score_role_composition_fanout` to
  validate only the requested role on demand if this proves disruptive in practice.

Regression coverage: `tests/test_shared_guitar_timeline.py::
test_build_consumes_a_current_composed_multi_track_fanout_record` (two tracks compose into
one chart, notes from both tracks present and correctly ordered/mapped through alignment,
not silently dropped to the primary track alone) and `::
test_composed_draft_goes_stale_when_the_composition_track_set_changes` (narrowing the
composition plan after a composed draft was built invalidates that draft). The existing
fail-closed regression test (composition selects multiple tracks, no composed record
exists yet) continues to pass with an updated, more specific error-message expectation.

### Remaining #232 work after this slice

1. **Bass fan-out consumption** (`score_fanout.py`) -- the next slice. Must first close
   Trap 2 (rebind `ReconciledBassChart`/`SourceDisagreementReport`/
   `_invalidate_stale_bass_derivatives` staleness to the fan-out output's own content
   identity, not `(score_sha256, track_index)` alone) before wiring in composed multi-track
   consumption, then apply the same "materialize as an ordinary single-track output"
   strategy used here. Land as its own PR, per the split already used for the two
   fail-closed guards and reaffirmed above.

   **Update (Trap 2 identity rebind landed, 2026-08-20):** `ReconciledBassChart` and
   `SourceDisagreementReport` gained the same two optional fields as
   `SharedGuitarDraftManifest` -- `composed_source_track_indices` and
   `composed_fanout_record_sha256` (both `None` together for the current ordinary
   single-track case, both set together once Bass consumption populates them).
   `_invalidate_stale_bass_derivatives` now compares a freshly computed current fan-out
   content identity (`score_fanout.py::_current_bass_composed_identity`, mirroring
   `shared_guitar.py::_current_composed_record_for_role`'s plan/record lookup but without
   materializing anything) against each derivative's stored composed fields, in addition
   to the existing `(score_sha256, track_index)` check. `reconcile_bass_sources` itself is
   unchanged and still never populates the composed fields -- consuming the composed
   multi-track stream for Bass (retiring
   `_reject_unconsumed_multi_track_bass_composition` and adding a
   `_materialize_composed_bass_source` equivalent) remains the next slice. Regression
   coverage: `tests/test_score_fanout_invalidation.py::
   test_composition_selecting_additional_bass_tracks_invalidates_a_matching_reconciliation`
   and `::test_growing_a_composed_bass_selection_invalidates_the_older_smaller_composed_reconciliation`.
2. **Full audit-checklist sweep** -- re-verify every other
   `source_track_index ==` / `track_index ==` comparison listed in the non-exhaustive
   checklist above (`reviewed_positions.py`, `reviewed_event_timing.py`,
   `reviewed_techniques.py`, `reviewed_chords.py`, `guitar_authoring.py`, `alignment.py`,
   `score_preview.py`, `chord_identity_ui.py`, `score_mapping_review.py`,
   `score_role_composition_workspace_status.py`) against the now-landed Lead/Rhythm design,
   not just Bass, before considering issue #232 fully closed.
3. **Song Workspace / CLI status surfacing** -- confirm the workspace status layer and any
   export-manifest UI correctly reflect a composed (vs. single-track) draft's provenance
   post-integration (`composed_source_track_indices` is now available on
   `SharedGuitarDraftManifest` for that purpose); this was out of scope for this slice.
