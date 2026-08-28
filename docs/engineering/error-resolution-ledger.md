# Engineering Error-Resolution Ledger

This ledger stores durable engineering memory for significant or recurring failure patterns. GitHub Issues/PRs remain the active work record; this file captures reusable root-cause knowledge so future development does not repeatedly rediscover the same class of defect.

Do not add every transient lint error or one-off typo. Add an entry when a failure is significant, recurring, safety/correctness relevant, or reveals a prevention rule worth preserving.

## Entry template

### ERR-YYYY-NNN — Short failure-pattern name

- **First observed:** YYYY-MM-DD
- **Last observed:** YYYY-MM-DD
- **Status:** active | mitigated | resolved | monitoring
- **GitHub references:** issue/PR/commit links or numbers
- **User-visible symptom:**
- **Failing check / evidence:**
- **Root cause:**
- **Affected surfaces:**
- **Why prior safeguards missed it:**
- **Corrective design pattern:**
- **Fix applied:**
- **Verification:**
- **Regression protection:**
- **Provenance / invalidation / safety boundary:**
- **Residual risk:**
- **Prevention rule:**

---

## ERR-2026-001 — Stale downstream derivative/readiness state after upstream authority changes

- **First observed:** 2026
- **Last observed:** 2026-08-18
- **Status:** monitoring
- **GitHub references:** #193 and related linked issues/PRs recorded there
- **User-visible symptom:** Downstream Bass/Lead/Rhythm, validation/XML/package, or Song Workspace readiness state can appear current after the upstream authority it depends on has changed.
- **Failing check / evidence:** Recurring defect pattern documented in GitHub issue #193 across regeneration, validation/XML/package staging, and Song Workspace readiness.
- **Root cause:** Derived artifacts/readiness state are not always bound strongly enough to the exact current upstream provenance/authority identity, allowing stale derivatives to survive an upstream replacement.
- **Affected surfaces:** Arrangement regeneration, validation, Rocksmith XML/export readiness, package staging, Song Workspace readiness/status, and other derived-authority chains.
- **Why prior safeguards missed it:** Local validity checks can prove that a derivative is internally well formed without proving it was generated from the current authoritative upstream state.
- **Corrective design pattern:** Bind downstream artifacts to current provenance/content identity wherever possible; when exact binding is unavailable, conservatively invalidate dependent derivatives before publishing replacement upstream authority.
- **Fix applied:** Multiple local fixes have been made historically; issue #193 remains the durable cross-cutting tracker.
- **Verification:** Regression tests should exercise upstream authority replacement and assert that every dependent derivative becomes stale/invalid until regenerated from the new authority.
- **Regression protection:** Keep provenance-binding and stale-invalidation tests near each derivative/readiness boundary and add cross-surface tests when the same pattern recurs.
- **Provenance / invalidation / safety boundary:** A downstream artifact must never silently become authoritative when its upstream identity or human review authority is stale.
- **Residual risk:** New derivative layers can reintroduce the pattern if they cache readiness without binding it to upstream identity.
- **Prevention rule:** Every new cached/derived readiness or authoring artifact must explicitly answer: "Which exact upstream authority identities make this current, and how is it invalidated when any of them change?"

## ERR-2026-002 — Merge completed before automated review finding was reconciled

- **First observed:** 2026-08-20
- **Last observed:** 2026-08-25
- **Status:** monitoring
- **GitHub references:** #193, PRs #404, #418, #419, and their focused repair series
- **User-visible symptom:** A merged feature can leave a post-merge automated review finding unresolved on `main`; PR #404 left contradictory automation state, PR #418 could fold a tie onto a lookalike from another composition track, and PR #419 left the integrated Lead/Rhythm authoring path on the primary track only.
- **Failing check / evidence:** Post-merge Codex review comments on PRs #404, #418, and #419 identified, respectively, contradictory authoritative status, lost per-note composition origin at the reviewed tie-fold boundary, and missing composed-source resolution in the real reviewed-authoring path.
- **Root cause:** Merge completion was treated as safe from workflow results without independently reconciling review timing/state. PR #404's review arrived asynchronously around the merge, while PRs #418 and #419 still had material unresolved findings when they merged despite successful required workflows. The status contract also validated required fields without validating consistency between the active change and continuation pointer.
- **Affected surfaces:** Scheduled-run selection, durable project status, and any future PR whose asynchronous review finishes after CI/merge.
- **Why prior safeguards missed it:** Green workflows do not themselves prove that asynchronous or unresolved review feedback has been reconciled, and the existing readiness check treated `active_change` and `next_continuation` as independent narrative fields.
- **Corrective design pattern:** Inspect reviews and unresolved threads independently of CI immediately before merge, recheck recently merged PRs during the next triage, keep exactly one structured active-PR authority (`active_change.pr_number`), and reject legacy duplicate pointers anywhere else in the status contract.
- **Fix applied:** The repair series removed duplicate structured pointers, reconciled stale roadmap prose, and finally made the roadmap queue issue-only. Readiness now rejects pull-request references and generic current-state claims there.
- **Verification:** Focused tests accept one valid `active_change.pr_number` and require deterministic readiness failures when either legacy pointer is reintroduced.
- **Regression protection:** `tests/test_automation_readiness.py` covers the sole valid active-PR source, forbidden legacy pointers, pull-request references in the issue queue, and generic current-open/pending/awaiting-merge claims.
- **Provenance / invalidation / safety boundary:** This changes automation metadata only; it does not alter musical, source, mapping, validation, export, or packaging authority.
- **Residual risk:** Asynchronous review findings can still arrive after merge; every run must continue checking recently merged PRs and repair substantive findings on a new branch.
- **Prevention rule:** `active_change` and live GitHub triage are the only operational pull-request authorities. `roadmap_issue_queue` is issue-only and must contain neither pull-request references nor cached current PR state. Recently merged PR review threads must be inspected even when required CI was green.

## ERR-2026-003 — Flattened composition notes lost per-note origin identity

- **First observed:** 2026-08-25
- **Last observed:** 2026-08-25
- **Status:** mitigated
- **GitHub references:** #193, #414, PR #418, and repair PR #419
- **User-visible symptom:** A tie-only note in a composed Bass/Lead/Rhythm stream could silently extend an adjacent same-position note from a different selected score track when its real predecessor had been excluded or was absent.
- **Failing check / evidence:** PR #418 review traced the defect to `score_fanout.py` and `shared_guitar.py` flattening `ComposedSourceNote` objects to bare `SourceNoteEvent` values before `reviewed_tie_folding.py` searched predecessor candidates.
- **Root cause:** The composition fan-out record retained `(source_track_index, event_index)`, but both single-track materializers discarded that pair. Exact timing, pitch, string, and fret were therefore insufficient to prove that a candidate belonged to the tie's originating composition track.
- **Affected surfaces:** Composed multi-track Bass, Lead, and Rhythm reviewed authoring and downstream Rocksmith XML tie handoff.
- **Why prior safeguards missed it:** Unit coverage exercised ordinary single-track exact ties and composed materialization separately, but did not carry or assert per-note composition origin through the flattened read model.
- **Corrective design pattern:** Preserve the exact composition source track/event pair as additive note provenance; require complete pairs and scope deterministic tie folding to one proven originating track.
- **Fix applied:** Both composition materializers now stamp the original track/event pair, reviewed export preserves it, and the tie planner refuses cross-track candidates while retaining ordinary single-track behavior.
- **Verification:** Focused Bass/Lead/Rhythm adapter and composition-materialization tests cover same-track success, cross-track fail-closed behavior, and partial-origin rejection.
- **Regression protection:** Materializer tests assert exact origin pairs; parameterized Lead/Rhythm plus Bass tests prove that adjacent cross-track lookalikes remain human-review gated.
- **Provenance / invalidation / safety boundary:** The fields are additive and do not grant timing, mapping, technique, chord, validation, export, or packaging authority.
- **Residual risk:** Older generated composed artifacts do not contain the new pair, but current materializers rebuild from the persisted composition record; any future flattening boundary must explicitly preserve it.
- **Prevention rule:** Never flatten a multi-source event into a shared single-track read model without carrying its original source track/event identity through every deterministic inference boundary.

## ERR-2026-004 — Integrated reviewed authoring bypassed the composed source

- **First observed:** 2026-08-25
- **Last observed:** 2026-08-25
- **Status:** active
- **GitHub references:** #193, PR #419, and repair PR #420
- **User-visible symptom:** A current multi-track Lead or Rhythm composition could lose every secondary-track note at the reviewed authoring/Rocksmith XML input boundary even though review, preview, and chart-build surfaces consumed the composed stream.
- **Failing check / evidence:** Post-merge triage of PR #419's unresolved review found that `_reviewed_arrangement_timing_locked` returned the base score-fan-out entry and `_load_current_source_locked` opened it directly; for Lead/Rhythm that entry names only the confirmed primary track.
- **Root cause:** Composed-source resolution was added to review, preview, and shared-guitar build call sites, but not to the later project-facing reviewed-export projection. The tie-folding adapter tests constructed `ReviewedExportArrangement` directly, so they proved downstream behavior without proving upstream project wiring.
- **Affected surfaces:** `reviewed_export_arrangement`, `reviewed_guitar_authoring_input`, and the reviewed Lead/Rhythm Rocksmith XML handoff. Bass is unaffected because composed Bass output is already named in the score-fan-out manifest.
- **Why prior safeguards missed it:** Materializer and adapter tests were separated across the boundary; no regression invoked the real project-facing authoring call with a current multi-track Lead/Rhythm composition.
- **Corrective design pattern:** Resolve one current source at the authority boundary, under the caller's existing transaction, and bind both its path and content hash before projecting downstream notes.
- **Fix applied:** The shared composition resolver now has explicit unlocked and already-locked entry points. Reviewed arrangement timing uses the locked form before source loading and projection, avoiding a nested non-reentrant score transaction.
- **Verification:** Seventy-two focused tests and 1,431 non-librosa repository tests pass locally; fresh CI remains the full-suite gate.
- **Regression protection:** `test_reviewed_guitar_authoring_consumes_the_current_composed_source` drives the actual project API for both Lead and Rhythm and asserts two-track notes, exact origin pairs, and composed-source hash binding.
- **Provenance / invalidation / safety boundary:** The repair selects an already reviewed, current composition record and creates no new musical, timing, validation, export, or package authority.
- **Residual risk:** Other future project-facing consumers can repeat the omission if they read base fan-out entries directly instead of using the shared resolver.
- **Prevention rule:** A downstream project API for a composable role must prove its source-selection path with an integration test; unit-testing only its post-projection model is insufficient.

## ERR-2026-005 — Workflow planner treated a stale alignment refinement as complete

- **First observed:** 2026-08-26 (packaged retest after PR #432)
- **Last observed:** 2026-08-28 (packaged retest after PR #436, issue comment on #431)
- **Status:** mitigated
- **GitHub references:** #193, #431, #437, PRs #432 and #436 (the refinement-algorithm fixes that this defect silently swallowed)
- **User-visible symptom:** Two successive Product Reality timing fixes for #431 (content-aware onset refinement v3/v4, then leading-rest-aware refinement v1/v5) shipped and passed CI, but a fresh packaged retest against the same already-aligned project reproduced the *identical* residual late-projection numbers (~11.773 s vs. the real ~7.109 s entrance) even after the user explicitly ran "Run Safe Automatic Steps" and re-promoted timing.
- **Failing check / evidence:** `build_project_workflow_plan`'s `align-tab` step read `_current_bass_alignment()` (source path/hash/track-index match only) and marked the step `complete` the instant `analysis/alignment.json` existed, with no check of refinement-algorithm currency. `alignment_onset_refinement.refinement_is_current()` already existed to detect exactly this staleness (mirroring `fret_mapping.bass_mapping_is_current()`) but had zero callers anywhere in the codebase, so it never influenced planning.
- **Root cause:** The refinement passes correctly ran and correctly updated `alignment.json` for *newly aligned* projects (`align_project_source` always calls both refinement passes), but a project that already had an `alignment.json` from before either refinement algorithm existed (or before a version bump) never re-entered the `align-tab` step, because the planner's staleness test ignored refinement identity entirely. The improved algorithm code was real and unit-tested in isolation, but never executed against the real, already-aligned Product Reality project.
- **Affected surfaces:** `workflow_plan.build_project_workflow_plan` (`align-tab`/`reconcile-tab` steps) and, transitively, every packaged "Run Safe Automatic Steps" pass on a project that was aligned before a refinement-algorithm upgrade.
- **Why prior safeguards missed it:** The `align-tab` currency check and the `map-bass` currency check (`bass_mapping_is_current`) were implemented independently; the mapping path got a currency guard against its algorithm version and downstream reconciliation, but the earlier alignment path did not receive the analogous guard when its own refinement passes were introduced. Unit tests for the refinement modules exercised the pure functions directly and never asserted anything about planner-visible readiness, so the missing wiring had no failing test.
- **Corrective design pattern:** Same as ERR-2026-001: bind a derived "complete" readiness state to the exact algorithm-version identity of every pass that can change it, not just to the existence of its output file.
- **Fix applied:** Added `leading_rest_refinement_is_current()` alongside the existing `refinement_is_current()`, and added `_bass_alignment_refinements_are_current()` in `workflow_plan.py` so `align-tab` (and the downstream `reconcile-tab`) only reads `complete` when both the onset-refinement and leading-rest-refinement evidence records exist, match the current algorithm version, and match the alignment's source hash/track index. Otherwise `align-tab` re-opens as `ready` with the same `cdlc align-source` command used for first-time alignment, and `reconcile-tab` is blocked until realignment completes.
- **Verification:** `python -m pytest -q` (1489 passed), `python -m compileall -q src tests`, `python scripts/check_automation_readiness.py`, `cdlc --help`, and `python scripts/quality_preflight.py` all pass locally on this change.
- **Regression protection:** `test_stale_alignment_refinement_reopens_align_tab_step` and `test_partially_stale_alignment_refinement_also_reopens_align_tab_step` in `tests/test_workflow_plan.py` drive the real planner against an alignment with missing/partial refinement evidence and assert `align-tab` reopens; `test_current_alignment_refinements_keep_align_tab_complete` proves the non-regression case; `test_refinement_is_current_requires_matching_record` and `test_leading_rest_refinement_is_current_requires_matching_record` directly cover the two previously-uncalled currency helpers.
- **Provenance / invalidation / safety boundary:** No musical, timing, validation, export, or package authority is created by this fix; it only changes which existing automatic step the planner offers, and re-running `align-source` still goes through the same human timing-review/promotion gate before any authority is trusted.
- **Residual risk:** This fix makes the *planner* re-offer alignment when refinement is stale; it does not by itself prove that the current onset/leading-rest refinement algorithm produces the musically correct shift for the private For Whom the Bell Tolls project referenced in #431 — that still requires a fresh packaged retest, now with confidence that the retest actually exercises the current refinement code.
- **Prevention rule:** Whenever a new content-aware refinement/correction pass is added over an existing artifact, its "is this current" check must be added to the planner step that gates re-running it in the same change, not left to be wired in later; a currency helper with no callers is itself a defect signal worth grepping for.

## Maintenance rules

- Cross-link recurring defects to GitHub issue #193 or a more specific root-cause issue.
- Prefer one root-cause entry over many symptom-only entries when failures share the same mechanism.
- Update an existing entry when new evidence changes the understood root cause or prevention rule.
- Do not rewrite history to make an earlier diagnosis look correct; preserve the evolution of the evidence in GitHub and summarize the current best-supported root cause here.
- Product Reality and major milestone issue sweeps should consult this ledger for unresolved sibling failure patterns.
