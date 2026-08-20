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
overlaps for, and composing this per-role note stream have since landed. The downstream
reconciliation/authoring/export consumer has since landed for all three roles as well: see
"Downstream consumption: Lead/Rhythm (landed)" and "Downstream consumption: Bass (landed)"
below. No commercial audio/DLC, private CFSM exports, Ubisoft-derived content, PSARC
packages, or generated private project data belong in this module or its tests.

**Update (Lead/Rhythm slice landed, issue #232):** `shared_guitar.py`'s Lead/Rhythm chart
build now consumes the composed multi-track note stream for a role, retiring
`_reject_unconsumed_multi_track_composition` in favor of
`_current_composed_record_for_role` (still fails closed the same way when a role's
composition selects more than one track but no current composed fan-out record exists yet
for that exact selection). See the "Downstream consumption: Lead/Rhythm (landed)" section
below for the implemented design.

**Update (Bass slice landed, issue #232):** `score_fanout.py`'s Bass fan-out now consumes
the composed multi-track note stream the same way, retiring
`_reject_unconsumed_multi_track_bass_composition` in favor of
`_current_composed_bass_record`, and closes Trap 2 (Bass derivative staleness previously
bound to `(score_sha256, track_index)` alone) by binding `ReconciledBassChart`/
`SourceDisagreementReport` invalidation to the fan-out output's own content hash as well.
See the "Downstream consumption: Bass (landed)" section below for the implemented design.
Both fail-closed guards referenced by this document are now fully retired.

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

1. **Full audit-checklist sweep** -- re-verify every other
   `source_track_index ==` / `track_index ==` comparison listed in the non-exhaustive
   checklist above (`reviewed_positions.py`, `reviewed_event_timing.py`,
   `reviewed_techniques.py`, `reviewed_chords.py`, `guitar_authoring.py`, `alignment.py`,
   `score_preview.py`, `chord_identity_ui.py`, `score_mapping_review.py`,
   `score_role_composition_workspace_status.py`) against the now-landed Lead/Rhythm and
   Bass designs, before considering issue #232 fully closed. Land as its own PR -- it is a
   distinct audit, not an extension of either landed slice.
2. **Song Workspace / CLI status surfacing** -- confirm the workspace status layer and any
   export-manifest UI correctly reflect a composed (vs. single-track) draft's provenance
   post-integration for both Lead/Rhythm (`composed_source_track_indices` is now available
   on `SharedGuitarDraftManifest` for that purpose) and Bass (which has no persisted draft
   manifest analogous to `SharedGuitarDraftManifest` today -- Bass fan-out output flows
   directly into `reconcile_project_bass`/`ReconciledBassChart` rather than through a
   cached, re-loadable draft, so surfacing composed-vs-single-track provenance for Bass
   needs its own design, not a direct reuse of the Lead/Rhythm manifest fields). Out of
   scope for both landed slices.

## Downstream consumption: Bass (landed)

This section documents the design actually implemented for `score_fanout.py`, following
the candidate strategy above and mirroring the Lead/Rhythm slice, and specifically how it
closes Trap 2.

- `_current_composed_bass_record(project, score=...)` replaces
  `_reject_unconsumed_multi_track_bass_composition`. It mirrors `shared_guitar.py`'s
  `_current_composed_record_for_role` exactly: returns `None` (ordinary single-track fan-
  out path, unchanged) whenever the persisted composition plan is missing/stale/unreadable
  or selects at most one track for Bass; loads the persisted fan-out layer through
  `score_role_composition_fanout_review._load_current_locked` as a **function-local**
  import (rather than a module-level one) specifically to avoid a circular import --
  `score_role_composition_fanout_review.py` already imports
  `_require_score_rights_review`/`_reviewed_score_path` from `score_fanout.py` at module
  scope, so a top-level import in the other direction would deadlock the import graph;
  fails closed with the same "no current composed fan-out record exists yet" message when
  Bass's composition selects more than one track but no matching current record exists.
- `_materialize_composed_bass_source(project, record=...)` builds the composed stream as
  one ordinary single-track `ImportedSource`, exactly per the candidate strategy and
  mirroring `_materialize_composed_guitar_source`: `tracks[0].notes` is
  `[item.note for item in record.notes]` (already start-time ordered), `source_track_index`
  is the confirmed primary (`record.source_track_indices[0]`), and score-level fields
  (`ticks_per_beat`, `tempo_events`, `time_signatures`, `beat_times_seconds`,
  `tuning_midi`) are cross-checked for exact equality across every contributing track's
  persisted per-track import before being trusted, failing closed on disagreement. The
  merged single-track source is written to
  `sources/imported/composition/bass-composed-<score_sha12>.json` and consumed exactly
  like the existing single-track fan-out output by `reconcile_project_bass`/
  `reconcile_bass_sources` and everything built on `ReconciledBassChart` -- none of those
  call sites changed.
- **Trap 2 is closed.** `ReconciledBassChart` and `SourceDisagreementReport` each gained an
  optional `source_content_sha256` field: the content hash of the exact single-track
  `ImportedSource` file the reconciliation/disagreement report was built from.
  `reconcile_project_bass` populates it from the `--source` file it was actually given;
  `reconcile_bass_sources` (the pure function) accepts it as an explicit optional
  parameter rather than deriving it, since it only ever sees an in-memory `ImportedSource`,
  not a file path. `score_fanout.py::_invalidate_stale_bass_derivatives` now requires this
  recorded hash to equal the just-produced Bass fan-out output's own content hash, in
  addition to the existing `(score_sha256, track_index)` check, before treating a prior
  Bass reconciliation/disagreement report as still current. A `None` on either side never
  counts as a match: an older reconciliation predating this field is conservatively
  invalidated on the next Bass fan-out rather than assumed still current by `track_index`
  alone. This closes the exact gap the design sketch identified: adding/removing/reordering
  a non-primary composed track leaves the confirmed *primary* track index unchanged, so the
  old `(score_sha256, track_index)`-only check would have incorrectly kept treating a
  reconciliation built from the prior, differently-composed note stream as current.
- Trap 1 (lock re-entrancy) is closed the same way as Lead/Rhythm: `_current_composed_bass_
  record` is called from inside `fanout_confirmed_score_mappings`'s already-held
  `score_mapping_transaction`, so it loads the fan-out layer through the lock-assuming
  `_load_current_locked` rather than the public transaction-opening
  `load_current_score_role_composition_fanout`.
- Known, deliberately out-of-scope limitation, inherited unchanged from the Lead/Rhythm
  slice and `_load_current_locked` itself: loading the fan-out layer validates every
  persisted role's composed record, not only Bass's. A stale/unrelated *other* role's
  composed record can therefore cause a Bass fan-out to raise even though only Bass is
  being fanned out. This always fails closed (never silently wrong), so it is left as-is.

Regression coverage: `tests/test_score_fanout_bass_composition_guard.py::
test_fanout_consumes_a_current_composed_multi_track_bass_record` (two tracks compose into
one Bass fan-out output, notes from both tracks present and correctly ordered, not silently
dropped to the primary track alone; the ordinary GuitarPro importer is never invoked) and
`::test_composition_narrowed_after_reconciliation_invalidates_stale_bass_derivatives` (Trap
2 regression: narrowing a composed selection back to the single primary track after a
reconciliation was persisted against the composed output invalidates that reconciliation
even though the primary track index never changed). The existing fail-closed regression
test continues to pass with an updated, more specific error-message expectation
(`test_fanout_fails_closed_when_composition_selects_multiple_bass_tracks_with_no_composed_
record`). `tests/test_score_fanout_invalidation.py` gained
`test_composed_content_change_invalidates_derivatives_even_when_score_and_track_match` and
`test_legacy_reconciliation_without_a_content_hash_is_treated_as_stale`, exercising the new
content-hash binding directly at the `_invalidate_stale_bass_derivatives` unit level.

## Audit-checklist sweep (issue #232, landed)

This is the "full audit-checklist sweep" tracked as remaining #232 work after both the
Lead/Rhythm and Bass downstream-consumption slices above: re-verifying every other
`source_track_index ==` / `track_index ==` call site in `reviewed_positions.py`,
`reviewed_event_timing.py`, `reviewed_techniques.py`, `reviewed_chords.py`,
`guitar_authoring.py`, `alignment.py`, `score_preview.py`, `chord_identity_ui.py`,
`score_mapping_review.py`, and `score_role_composition_workspace_status.py` against the
now-landed designs, per-file:

- **Safe as-is, no change needed:**
  - `alignment.py` -- its `track_index ==` lookup always resolves a source's *single*
    track (alignment is computed once against the confirmed primary track before
    composition is layered on top); composition never changes which track alignment
    itself reads.
  - `guitar_authoring.py` -- its `track_index ==` filter matches the confirmed primary
    index of whatever single-track `ImportedSource` it is handed, which is exactly what
    `_materialize_composed_guitar_source`/`_materialize_composed_bass_source` already
    produce for a composed role. `build_guitar_authoring_chart` never needs to know
    whether that source was composed.
  - `score_mapping_review.py` -- its `==` comparisons confirm/replace one role's primary
    *mapping*, unrelated to fanned-out note-stream content.
  - `score_role_composition_workspace_status.py` -- its `==` comparison is a cosmetic
    score-track display-name lookup, unrelated to fanned-out note-stream content.
  - `reviewed_positions.py` / `reviewed_event_timing.py` / `reviewed_techniques.py` /
    `reviewed_chords.py`'s `apply_reviewed_*_to_source` functions (the ones actually called
    from inside `_build_project_shared_guitar_chart_locked`/Bass fan-out with a *composed*
    source) -- these already re-check each decision's recorded MIDI/onset/duration/
    technique content against the live note at that event index before applying it, and
    fail closed ("... identity is stale for current fan-out") on any mismatch. That
    per-event content check, not `source_track_index` equality alone, is what actually
    protects them once a composed note stream reorders events; it needed no further
    hardening.

- **Gap found and closed:** `reviewed_positions.py`'s `_fanout_entry`/`_source_event` --
  shared by `set_reviewed_position`, `set_reviewed_event_timing`, `set_reviewed_techniques`,
  `set_reviewed_chord_group`, and `reviewed_event_timing.py`/`reviewed_techniques.py`/
  `reviewed_chords.py`'s per-decision `validate_decision_identity` staleness re-checks --
  and `score_preview.py`'s `load_score_fanout_preview_snapshot` (the read model behind the
  Song Workspace "Arrangement Preview" tab and, transitively, `chord_identity_ui.py`) all
  read a role's note stream exclusively through the score fan-out manifest
  (`ScoreFanoutManifest.arrangements[].output_json`). Bass's composed multi-track fan-out is
  materialized directly into that manifest (see "Downstream consumption: Bass (landed)"
  above), so these correctly see composed Bass content. Lead/Rhythm's composed multi-track
  note stream is instead materialized only inside `shared_guitar.py`'s chart-build path
  (`_materialize_composed_guitar_source`, written to
  `sources/imported/composition/<role>-composed-<sha12>.json`) and **never written back
  into the score fan-out manifest** -- so for a Lead/Rhythm role with a multi-track
  composition selected, these four review layers and the Arrangement Preview would have
  kept reading and offering for review only the single confirmed-primary-track fan-out
  output, silently leaving every additional composed track's notes unreviewable through
  this surface, with no signal anything was left out. This is exactly the class of
  silent-undercount gap issue #232's fail-closed guards exist to prevent, reintroduced at a
  layer neither landed slice touched.

  Closed via a new shared helper, `reviewed_positions.composed_multi_track_review_gap`: a
  best-effort check (missing/stale/unreadable composition plan is "nothing to guard
  against here", mirroring `_current_composed_bass_record`/
  `_current_composed_record_for_role`) that compares a fan-out entry's `output_json` against
  the deterministic composed-source path (`sources/imported/composition/
  <role>-composed-<score_sha12>.json`) whenever that role's persisted composition plan
  currently selects more than one track. A mismatch -- which never happens for Bass, since
  its manifest entry already names that exact path once composed -- fails closed with an
  actionable message instead of silently reviewing/previewing an incomplete note stream.
  `_fanout_entry` calls it once, so every one of the four `set_reviewed_*` write paths and
  every `validate_decision_identity` re-check inherit the guard from one call site;
  `load_score_fanout_preview_snapshot` calls it per role in its own assembly loop.

  Regression coverage: `tests/test_shared_guitar_timeline.py::
  test_set_reviewed_position_fails_closed_for_an_unmaterialized_composed_lead_selection`
  and `::test_set_reviewed_position_is_unaffected_by_a_single_track_lead_composition_
  selection`; `tests/test_score_fanout_bass_composition_guard.py::
  test_set_reviewed_position_accepts_a_composed_bass_selection_after_fanout` (Bass, after a
  real composed fan-out run, is never blocked); `tests/test_score_preview.py::
  test_score_fanout_preview_fails_closed_for_an_unmaterialized_composed_lead_selection`,
  `::test_score_fanout_preview_accepts_a_composed_bass_selection_reflected_in_the_manifest`,
  `::test_score_fanout_preview_is_unaffected_by_a_single_track_lead_composition_selection`,
  and `::test_score_fanout_preview_ignores_a_stale_or_corrupt_composition_plan_file`.
  `reviewed_techniques.py`'s `set_reviewed_techniques` and `reviewed_event_timing.py`'s
  `set_reviewed_event_timing` were manually verified to inherit the same guard through the
  shared `_fanout_entry` choke point (both raise the identical fail-closed message for the
  same fixture); `reviewed_chords.py`'s `set_reviewed_chord_group` routes through the exact
  same `_source_event` call.

  **This gap is now closed.** Actually making position/timing/technique/chord review and
  the Arrangement Preview *consume* a role's composed multi-track note stream (rather than
  failing closed when one is selected) is documented in "Downstream consumption:
  position/event-timing/technique/chord review and the Arrangement Preview (landed)"
  below.

## Downstream consumption: position/event-timing/technique/chord review and the Arrangement Preview (landed)

This lands the last remaining item of issue #232 flagged at the end of the audit-checklist
sweep above: position, event-timing, technique, and chord review, plus the Arrangement
Preview, now actually *consume* a role's composed multi-track note stream once one has
been composed, instead of always failing closed when a multi-track composition is
currently selected.

- `reviewed_positions.py`'s `composed_multi_track_review_gap` (detection-only) is replaced
  by `resolve_composed_review_entry(project, arrangement, *, score, entry)`, called once
  from the shared `_fanout_entry` choke point (inherited by every `set_reviewed_*`/
  `apply_reviewed_*_to_source` write path in this module and
  `reviewed_event_timing.py`/`reviewed_techniques.py`/`reviewed_chords.py`/
  `chord_fingering.py`) and once per role from `score_preview.py`'s
  `load_score_fanout_preview_snapshot` assembly loop -- the same two call sites the
  detection-only guard used.
- For Bass, `entry.output_json` already names the composed stream (materialized directly
  into the score fan-out manifest, "Downstream consumption: Bass (landed)" above), so this
  returns `entry` unchanged after verifying that invariant still holds -- Bass's behavior
  is unaffected by this slice, exactly as the guard already treated it.
- For Lead/Rhythm with a role's persisted composition currently selecting more than one
  track, this loads the current `RoleCompositionFanoutRecord` (the public,
  lock-opening `score_role_composition_fanout_review.
  load_current_score_role_composition_fanout` -- none of these call sites hold the project
  lock already) and re-materializes the exact same composed source
  `shared_guitar.py`'s chart-build path uses (`_materialize_composed_guitar_source`,
  imported via a function-local import to avoid a circular import, the same pattern
  `score_fanout.py` already uses for the equivalent Bass case), then returns a copy of
  `entry` with `output_json` pointing at it. No event-index-keying logic in any of the four
  review layers, `score_preview.py`'s note assembly, or `chord_fingering.py` needed to
  change: the composed source is already an ordinary single-track `ImportedSource` shaped
  exactly like any other fan-out output (confirmed-primary `source_track_index`,
  start-time-ordered notes), which is what every one of those event-index-keyed consumers
  already expected -- only *which* file `_fanout_entry`/`load_score_fanout_preview_snapshot`
  resolve had to change. This mirrors, and closes, the exact gap the "Downstream
  consumption: Lead/Rhythm (landed)" and "Audit-checklist sweep" sections above describe.
- A role's composition selecting more than one track with no current composed fan-out
  record yet still fails closed, unchanged in substance from the guard this replaces (only
  the message text is slightly more specific): reviewing/previewing against a
  not-yet-composed selection would either silently target the wrong stream or surface only
  as an opaque staleness mismatch much later. This genuinely ambiguous/unbuilt case is not
  weakened by this slice.
- Recomposing or narrowing a role's composition after a reviewed decision was recorded
  against a composed stream is not separately re-validated here: the existing per-decision
  content check each `apply_reviewed_*_to_source` already performs (matching recorded
  MIDI/onset/duration/technique against the live note at that event index, failing closed
  as "... identity is stale for current fan-out" on any mismatch) already covers this, as
  the audit-checklist sweep above established -- no further hardening was needed or added.

Regression coverage: `tests/test_shared_guitar_timeline.py::
test_set_reviewed_position_fails_closed_for_an_uncomposed_lead_selection` (renamed/updated
from the prior detection-only guard's fail-closed test -- a Lead composition selecting more
than one track with no composed record yet still fails closed),
`::test_set_reviewed_position_consumes_a_current_composed_lead_selection` (once composed,
position review reads and records against the merged two-track stream, and the built chart
carries both reviewed decisions), and
`::test_set_reviewed_position_consumes_a_current_composed_rhythm_selection` (the same
behavior for Rhythm, not only Lead). `tests/test_score_preview.py::
test_score_fanout_preview_fails_closed_for_an_uncomposed_lead_selection` (renamed/updated)
and `::test_score_fanout_preview_consumes_a_current_composed_lead_selection` (the
Arrangement Preview shows both composed tracks' notes, not only the confirmed-primary
track's one note). Bass's existing composed-consumption coverage
(`tests/test_score_fanout_bass_composition_guard.py::
test_set_reviewed_position_accepts_a_composed_bass_selection_after_fanout`) continues to
pass unchanged, confirming this slice did not regress Bass's already-working path.

**Issue #232 is now fully landed**: every item recorded in this document's "Remaining #232
work" notes (Lead/Rhythm downstream consumption, Bass downstream consumption, the
audit-checklist sweep, Lead/Rhythm and Bass Song Workspace draft-provenance status
surfacing, and this review-layer/Arrangement-Preview consumption slice) is complete.

## Song Workspace status surfacing: Lead/Rhythm draft provenance (landed)

This lands the Lead/Rhythm half of the remaining "Song Workspace / CLI status surfacing"
item recorded above: confirming a human can see, without reading files by hand, whether a
role's *built* shared-guitar chart draft (`SharedGuitarDraftManifest`, in
`charts/<role>_shared_timeline.json`) currently reflects its composition intent -- a
distinct question from whether the fan-out layer has a current composed record for that
selection (`CompositionWorkspaceState`/`multi_track_composed`, which was already surfaced).
A role can be `multi_track_composed` at the fan-out layer while its built draft is still
stale because it has not been rebuilt since, or was built before the composition selection
last changed.

`score_role_composition_workspace_status.py`'s `ScoreRoleCompositionWorkspaceItem` gained
two new read-only fields, `draft_state` and `draft_stale_detail`:

- `draft_state` is one of `not_applicable`, `not_built`, `current_single_track`,
  `current_composed`, or `stale`. It is computed by a new best-effort helper,
  `_draft_status`, that calls `shared_guitar.load_current_shared_guitar_draft` for Lead/
  Rhythm roles: a missing manifest file is `not_built`; any `ValueError` it raises (the
  exact same staleness checks `shared_guitar_draft_is_current` already performs -- shared
  timeline, reviewed-layer, source, and composed-source-set/content currentness, among
  others) is caught and reported as `stale` with the underlying message preserved verbatim
  in `draft_stale_detail`, rather than raised; a current manifest reports
  `current_composed` or `current_single_track` depending on whether
  `composed_source_track_indices` is set.
- Bass always reports `draft_state == "not_applicable"` (with no stale detail). Bass has no
  persisted draft manifest analogous to `SharedGuitarDraftManifest` today -- its fan-out
  output flows directly into `reconcile_project_bass`/`ReconciledBassChart` instead of
  through a cached, re-loadable draft -- so surfacing composed-vs-single-track *draft*
  provenance for Bass still needs its own design and remains open, unchanged from the
  "Remaining #232 work" note above.
- This is read-only status: it never builds, rebuilds, or invalidates a draft, and never
  changes which draft/fan-out layer is authoritative. It only reads and reports what
  already exists, mirroring every other best-effort check in this module.

Regression coverage added in `tests/test_shared_guitar_timeline.py`:
`test_workspace_status_reports_bass_draft_as_not_applicable`,
`test_workspace_status_reports_lead_draft_not_built_before_first_build`,
`test_workspace_status_reports_a_current_single_track_lead_draft`,
`test_workspace_status_reports_a_current_composed_lead_draft`, and
`test_workspace_status_reports_a_stale_composed_lead_draft_detail` (narrowing the
composition plan after a composed draft was built surfaces `stale` with a non-empty
detail, rather than silently continuing to report `current_composed`).

**Remaining #232 work after this slice:** a Bass-side equivalent of
`SharedGuitarDraftManifest.composed_source_track_indices`/draft-provenance surfacing (its
own design, not a direct reuse of these Lead/Rhythm fields), and the larger downstream
review-layer/Arrangement-Preview consumption follow-on recorded above.

## Song Workspace status surfacing: Bass draft provenance (landed)

This lands the Bass half of the "Song Workspace / CLI status surfacing" item, closing the
gap the Lead/Rhythm slice above left open: Bass has no persisted draft manifest analogous
to `SharedGuitarDraftManifest` -- its fan-out output flows directly into
`reconcile_project_bass`/`ReconciledBassChart` instead of a cached, re-loadable draft --
so it needed its own design rather than reusing the Lead/Rhythm manifest fields.

`score_role_composition_workspace_status.py`'s `_draft_status` now branches Bass to a new
`_bass_draft_status` helper that reads `charts/bass_reconciled.json`
(`ReconciledBassChart`) as Bass's draft equivalent:

- A missing reconciliation file is `not_built`, matching the Lead/Rhythm convention (this
  replaces the prior permanent `not_applicable` placeholder for Bass).
- An unreadable/corrupt reconciliation file is `stale` with the parse error preserved
  verbatim in `draft_stale_detail`.
- A readable reconciliation is treated as current using exactly the same identity check
  `score_fanout.py::_invalidate_stale_bass_derivatives` already uses to decide whether a
  prior reconciliation survives a new fan-out: matching registered score
  (`source_sha256`), matching confirmed primary track index (`track_index`), and a
  matching content hash of the *current* Bass fan-out output
  (`ReconciledBassChart.source_content_sha256` against a freshly computed hash of the
  score fan-out manifest's current `bass` entry). A `None` content hash, a missing/
  unreadable fan-out manifest, or a missing output file all count as "does not match"
  rather than a free pass -- mirroring the conservative `None`-never-matches rule that
  closed Trap 2 for fan-out invalidation itself. Anything else is `stale` with an
  actionable `draft_stale_detail`.
- Because a composed Bass fan-out is materialized directly into the score fan-out
  manifest itself (unlike Lead/Rhythm, whose composed output lives only inside the
  shared-guitar chart-build path -- see "Downstream consumption: Bass (landed)" above),
  once the content hash matches, whether the reconciliation reflects a composed or
  single-track selection is read directly off which output file that content hash
  belongs to (`sources/imported/composition/bass-composed-<score_sha12>.json` vs. an
  ordinary single-track fan-out output), rather than off the *current* composition
  selection. A composition edited after the last fan-out/reconciliation run therefore
  correctly leaves this reporting what was actually built and reconciled, while
  `CompositionWorkspaceState` elsewhere already surfaces that composition intent has
  moved on -- the same current-vs-intent split the Lead/Rhythm slice already draws.

Regression coverage added in `tests/test_score_fanout_bass_composition_guard.py`:
`test_workspace_status_reports_bass_draft_not_built_before_reconciliation`,
`test_workspace_status_reports_a_current_single_track_bass_draft`,
`test_workspace_status_reports_a_current_composed_bass_draft`,
`test_workspace_status_reports_a_stale_bass_draft_when_content_hash_disagrees`,
`test_workspace_status_reports_a_stale_bass_draft_with_no_recorded_content_hash`,
`test_workspace_status_reports_bass_draft_stale_when_no_current_fanout_output_exists`, and
`test_workspace_status_reports_a_corrupt_bass_reconciliation_file_as_stale`. The existing
Lead/Rhythm draft-state test in `tests/test_shared_guitar_timeline.py` was updated
(`test_workspace_status_reports_bass_draft_not_built_before_reconciliation`, formerly
`test_workspace_status_reports_bass_draft_as_not_applicable`) to expect the new `not_built`
behavior instead of the retired permanent `not_applicable` placeholder.

**Remaining #232 work after this slice:** only the larger downstream review-layer/
Arrangement-Preview consumption follow-on recorded above (making position/timing/
technique/chord review and the Arrangement Preview actually consume a role's composed
multi-track note stream, rather than failing closed when one is selected). Both halves of
"Song Workspace / CLI status surfacing" (Lead/Rhythm and Bass) are now landed.

**Update:** that remaining follow-on has since landed too -- see "Downstream consumption:
position/event-timing/technique/chord review and the Arrangement Preview (landed)" above.
Issue #232 is now fully landed.
