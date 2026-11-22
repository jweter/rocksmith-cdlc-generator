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

## ERR-2026-006 — Repeated heuristic repair despite a working mature behavioral oracle

- **First observed:** 2026-08-24
- **Last observed:** 2026-08-28
- **Status:** active
- **GitHub references:** #193, #414, #431, #455, PRs #413, #432, #436
- **User-visible symptom:** The same lawful Guitar Pro score and recording stay correctly synchronized in Editor on Fire while successive packaged Rocksmith CDLC Generator builds remain late. After the initial large error was reduced, the representative build still projects the common Bass/Lead/Rhythm entrance at ~11.773 s instead of ~7.109 s and places a later printed-score Lead landmark about two bars late.
- **Failing check / evidence:** PR #413 adopted only EOF's pre-zero/pre-roll semantic boundary, then PRs #432 and #436 added project-specific periodic-onset and leading-rest-ranking heuristics around the existing alignment engine. After ERR-2026-005 was fixed so v5 actually reran, the 2026-08-28 packaged Product Reality test still reproduced the timing disagreement. EOF remained correct on the same input throughout.
- **Root cause:** The engineering path treated the existing custom alignment architecture as something to preserve and incrementally tune even after the mature reference implementation had already demonstrated the required semantics. That caused repeated optimization of heuristic candidate ranking instead of replacing the defective decision boundary with a direct parity/adaptation slice.
- **Affected surfaces:** Guitar Pro score-to-recording synchronization, all three shared arrangements derived from that clock, Product Reality iteration time, and human test burden.
- **Why prior safeguards missed it:** Unit tests could prove that each heuristic behaved as designed on synthetic fixtures, but those tests did not prove behavioral equivalence to EOF on the failure class that mattered. The mature-reference-first rule in #414 existed, but it was applied as a source of isolated ideas rather than as a stopping rule against further speculative heuristics.
- **Corrective design pattern:** When a lawful same-input differential test shows a mature implementation is correct and the local implementation is wrong, establish a narrow parity target first. Port/adapt the relevant licensed behavior or make the mature implementation an explicit oracle; only layer higher-level automation after parity is demonstrated.
- **Fix applied:** Issue #455 introduces alignment v6 for Guitar Pro. The GP path stops running the old periodic global-shift and leading-rest-distance refinement heuristics and instead establishes one first synchronization point from the earliest strongly supported complete-score onset prefix, then translates the shared beat map with the current EOF `gp_import.c` pre-zero semantics. The exact upstream repository/path/SHA are recorded in code and generated evidence.
- **Verification:** Synthetic regression added for the exact residual failure shape: a first event projected to 11.773 s, the real complete prefix at 7.109 s, an equally plausible later repeat at 11.773 s, and a deliberately weak/wrong first pitch estimate. Packaged Windows Product Reality verification is still required before this entry can move out of active status.
- **Regression protection:** `tests/test_eof_first_sync_alignment.py` requires the earlier supported occurrence to win, requires an approximately -4.664 s correction without song/title constants, and verifies that insufficient onset evidence fails closed without emitting planner-completion markers.
- **Provenance / invalidation / safety boundary:** EOF project code is BSD-style licensed and the exact current upstream SHA/path are recorded in `THIRD_PARTY_NOTICES.md`. The implementation does not bundle EOF or private song material. Downstream timing/review/arrangement derivatives are invalidated after the new timing decision and still require the existing human promotion gate.
- **Residual risk:** The audio-side identification of the first synchronization point is still our automated replacement for a human/Go-PlayAlong sync point; EOF itself does not magically infer arbitrary commercial recording alignment from a GP file. Therefore packaged parity must validate both the first entrance and later landmarks before claiming the defect fixed.
- **Prevention rule:** After two failed heuristic repairs against a same-input mature oracle, stop adding ranking knobs. Make direct behavioral parity/adaptation the next change, pin the upstream implementation used, and require a differential Product Reality acceptance test before resuming feature work.

## ERR-2026-007 — Notebook tab content packed by multiple mixins exceeded the visible viewport with no scroll path

- **First observed:** 2026-08-26 (Score & Mappings tab, issue #304)
- **Last observed:** 2026-08-30 (packaged acceptance for Arrangement Preview, issue #454)
- **Status:** resolved
- **GitHub references:** #193, #305, #304, #454
- **User-visible symptom:** On a laptop-resolution window with Windows display scaling, packaged Product Reality testing on 2026-08-28 confirmed the Arrangement Preview tab's content extended below the visible application window with no way to reach the rest of the page.
- **Failing check / evidence:** User screenshots on 2026-08-28 plus issue #454's reproduction steps. The same underlying shape had already appeared in the Score & Mappings tab in issue #304.
- **Root cause:** `ttk.Notebook` tab frames size to their available space, but plain `pack(fill="x", ...)` children inside a tab do not themselves scroll. Arrangement Preview is built incrementally by multiple mixins, each unaware of the total vertical space used by sibling mixins.
- **Affected surfaces:** `arrangement_preview_ui.py` and every mixin that packs into `self.arrangement_preview_tab`. Any other notebook tab built by the same incremental-mixin pattern is exposed.
- **Why prior safeguards missed it:** The earlier Score & Mappings fix addressed tall individual children but did not establish a page-level scroll convention for tabs whose combined content exceeds the viewport.
- **Corrective design pattern:** Wrap the whole notebook tab body in a `Canvas` + vertical `Scrollbar`, re-parent the content frame through `create_window`, pin content width to the viewport, recompute the scroll region on content size changes, and scope mousewheel handling to the active page.
- **Fix applied:** `ArrangementPreviewSongWorkspaceWindow._build_scrollable_arrangement_preview_tab` in `arrangement_preview_ui.py`.
- **Verification:** Deterministic UI regression coverage passed in the implementation change, and the 2026-08-30 packaged laptop Product Reality session confirmed the scrollbars are present and usable.
- **Regression protection:** `tests/test_arrangement_preview_scroll_ui.py` covers the page-level wiring; `tests/test_desktop_score_tab_layout.py` continues to cover the Score & Mappings tab's per-widget scrollbars.
- **Provenance / invalidation / safety boundary:** Presentation-only change; no musical, timing, mapping, validation, export, or package authority is affected.
- **Residual risk:** Other notebook tabs assembled by multiple mixins still need explicit viewport audits.
- **Prevention rule:** Any `ttk.Notebook` tab whose content is assembled by more than one mixin/override packing widgets vertically must either get a page-level scroll wrapper up front or be explicitly tested at the minimum supported window size whenever new content is added.

## ERR-2026-008 — Human review gate depended on the artifact created by that review

- **First observed:** 2026-08-30
- **Last observed:** 2026-08-30
- **Status:** active
- **GitHub references:** #193, #431, #455, #457, #480, PR #481
- **User-visible symptom:** The packaged Song Workspace reached `Review & Promote Timing`, showed the recording waveform/beat grid, and correctly withheld downstream Lead/Rhythm drafts, but Arrangement Preview displayed `shared_timeline.json` missing and no score notes. The human therefore could not verify the ~7.109 s first entrance or later Lead landmark before being asked to approve timing.
- **Failing check / evidence:** 2026-08-30 packaged laptop screenshots. Overview showed shared timing `Not promoted yet`; Arrangement Preview reported the missing promoted timeline; Validation and Review Queue had no downstream material yet.
- **Root cause:** `load_score_fanout_preview_snapshot()` is a read-only human-review surface but called `alignment_for_role()`, which is intentionally a post-promotion authority API that requires `analysis/shared_timeline.json`. The preview thus required the artifact that only the preview's human decision was allowed to create.
- **Affected surfaces:** Arrangement Preview, timing Product Reality acceptance, and the human-review boundary for the shared recording clock.
- **Why prior safeguards missed it:** Unit coverage proved the post-promotion preview and promotion button independently. No test asserted the end-to-end authority order: the human must be able to inspect the exact candidate musical events *before* the promotion artifact exists.
- **Corrective design pattern:** Separate **candidate read models** from **promoted authority models**. A human gate may render a validated, provenance-bound candidate without granting authority; promotion remains an explicit write. If promoted authority exists but is stale, fail closed rather than falling back and hiding the stale state.
- **Fix applied:** PR #481 adds a preview-only resolver in `score_preview.py`. It keeps `alignment_for_role()` as the first/authoritative path, but when no promoted timeline file exists it materializes the exact `build_shared_timeline_candidate()` transform onto each current role's validated fan-out source for display only.
- **Verification:** Fresh CI/Windows Desktop plus packaged Product Reality are required. The packaged acceptance must show candidate notes before promotion and then verify the first common entrance near ~7.109 s, the later Lead landmark around ~77.756 s, and no later drift.
- **Regression protection:** `tests/test_score_preview_pre_promotion.py` covers candidate materialization, no promotion side effect, normal promoted behavior, and fail-closed handling when a promoted timeline file exists but its dependencies are broken.
- **Provenance / invalidation / safety boundary:** Candidate preview does not write `shared_timeline.json`, create human timing authority, bypass validation, or change EOF-derived timing semantics. Role-specific source identity remains bound to the current score fan-out/mapping checks.
- **Residual risk:** A future human gate can repeat this architectural mistake if its read path calls only post-approval APIs. Packaged Windows testing is still required because CI cannot prove the review experience is understandable or the private song landmarks are correct.
- **Prevention rule:** For every human approval gate, write an explicit test for the state immediately *before* approval: the user must be able to inspect the exact candidate being approved without first creating the authority artifact that approval controls.

## ERR-2026-009 — Automation-readiness contract rejected the legitimate no-active-PR state

- **First observed:** 2026-09-01
- **Last observed:** 2026-09-01
- **Status:** resolved
- **GitHub references:** #193, ERR-2026-002 (origin of this validator)
- **User-visible symptom:** CI's "CI" workflow failed on `main` at commit `7012b25` (a docs-only project-status reconciliation commit) with `AUTOMATION READINESS: FAIL - active_change.pr_number must be a positive integer`, even though no PR was open and `docs/project-status.yaml` correctly declared `active_change: {pr_number: null, state: "none"}`. Both the Windows and Ubuntu CI jobs failed identically, masking the same underlying `tests/test_automation_readiness.py` failures the fix in ERR-2026-002 was meant to protect.
- **Failing check / evidence:** `scripts/check_automation_readiness.py::check_status_contract` unconditionally required `active_change.pr_number` to be a positive integer whenever `active_change` was present as a mapping, with no exemption for `pr_number: null`. Because `check_status_contract` raised before reaching the later `next_continuation`/`verified_repository_state`/`roadmap_issue_queue` checks, every other test in `tests/test_automation_readiness.py` that `deepcopy`s the real status and mutates one specific field also failed, each with the wrong (generic) error message instead of its expected specific one. 8 of 9 tests in the file failed in both CI jobs.
- **Root cause:** ERR-2026-002's fix correctly enforced "exactly one structured active-PR authority," but its implementation treated `active_change` being a dict as itself sufficient to require a real PR number, rather than requiring a real PR number only when one is actually claimed (`pr_number` not `None`). The legitimate steady state — no active change, `pr_number: null` — was never covered by a regression test, so the gap shipped unnoticed until a routine docs commit exercised it.
- **Affected surfaces:** `scripts/check_automation_readiness.py` (the `Verify autonomous-development contract` CI step) and, transitively, every PR's CI run while `main`'s `docs/project-status.yaml` has no active change.
- **Why prior safeguards missed it:** `tests/test_automation_readiness.py::test_automation_readiness_contract_passes` runs the checker against the real repository file, but at the time ERR-2026-002 landed, `main`'s `active_change.pr_number` happened to be a real integer (an in-flight PR), so the `None` path was never exercised until a later commit legitimately reset `active_change` to `state: "none"`.
- **Corrective design pattern:** Only validate a field's shape/value when it is actually populated; a `null`/absent optional field is a distinct, valid case from "populated but wrong," and both must have explicit test coverage.
- **Fix applied:** Changed the guard to `if active_pr is not None and (not isinstance(active_pr, int) or active_pr <= 0): fail(...)`, so `pr_number: null` is accepted and a present-but-invalid value is still rejected.
- **Verification:** `python -m pytest -q tests/test_automation_readiness.py` (9 passed) and `python scripts/check_automation_readiness.py` (`AUTOMATION READINESS: PASS`) both verified locally against the real `docs/project-status.yaml`.
- **Regression protection:** `tests/test_automation_readiness.py::test_automation_readiness_contract_passes` now exercises the real `pr_number: null` steady state on every run; no new test was needed since this is the existing test the fix repairs.
- **Provenance / invalidation / safety boundary:** Automation metadata only; no musical, source, mapping, validation, export, or packaging authority is affected.
- **Residual risk:** Any future optional field added to `active_change` (or similar structured status blocks) can repeat this pattern if its "unset" state is not exercised by `test_automation_readiness_contract_passes` against the live file.
- **Prevention rule:** When a status-contract check gains a "must be a positive integer" (or similarly typed) rule for a field that is also legitimately `null`/absent, the null/absent case must be an explicit branch, not an accident of whatever value happens to be in the repository when the rule is written.

## ERR-2026-010 — Preflight-promotion gate's gh CLI had no repository context

- **First observed:** 2026-09-10 (first `Verify Preflight-Green Branch` run for PR #568's branch)
- **Last observed:** 2026-09-11 (run 174, workflow_run triggered by the `Preflight` run for PR #573's branch)
- **Status:** mitigated
- **GitHub references:** #193; observed across PR #554, #556, #558, #566, #567, #568, #571, #572, #573
- **User-visible symptom:** `Verify Preflight-Green Branch` (`.github/workflows/promote-preflight-green.yml`) reported `conclusion: failure` on every `orchestrator/*`/`agent/*` branch whose `Preflight` run succeeded, so no draft PR was ever auto-promoted to ready-for-review by this gate.
- **Failing check / evidence:** Job `verify-promotion-gate`, step "Download exact-head preflight evidence", failed with `failed to run git: fatal: not a git repository (or any of the parent directories): .git` before `gh run download` could run, e.g. run 34558783323 (https://github.com/jweter/rocksmith-cdlc-generator/actions/runs/34558783323/job/103137010509).
- **Root cause:** The job has no `actions/checkout` step (intentional: it verifies evidence without executing branch code). `gh run download` and the later `gh pr list`/`gh pr view`/`gh pr ready` calls had no `--repo` flag and no `GH_REPO` env var, so the `gh` CLI tried to infer the target repository from the current directory's git remote, found no `.git` at all, and failed before ever contacting the GitHub API.
- **Affected surfaces:** `.github/workflows/promote-preflight-green.yml` only. No product code, timing, export, or validation authority is involved.
- **Why prior safeguards missed it:** The workflow was added and presumably exercised once against a real promotion, but nothing re-ran it end-to-end on a later `orchestrator/*`/`agent/*` preflight success until live GitHub state was inspected directly; there was no regression test parsing the workflow's own repo-context wiring.
- **Corrective design pattern:** Any job that intentionally skips `actions/checkout` but still calls `gh` must supply repository context explicitly (`GH_REPO` env at the job level, or `--repo owner/name` per invocation) rather than relying on `gh`'s local-git auto-detection.
- **Fix applied:** Added `env: GH_REPO: ${{ github.repository }}` at the `verify-promotion-gate` job level, which supplies repo context to every `gh` invocation in the job (download, list, view, ready) without adding a checkout step.
- **Verification:** `python -m pytest -q tests/test_promote_preflight_green_workflow.py` passes against the fixed workflow and was confirmed to fail with the exact pre-fix symptom when run against the unpatched file (via `git stash` of only this workflow file). `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/promote-preflight-green.yml'))"` confirms the edited file still parses as valid YAML.
- **Regression protection:** `tests/test_promote_preflight_green_workflow.py` asserts the job still has no checkout step and that `GH_REPO` (or an explicit `--repo`) is present wherever the job invokes `gh`.
- **Provenance / invalidation / safety boundary:** CI/automation metadata only; grants no musical, timing, mapping, validation, export, or packaging authority, and does not touch the evidence-integrity checks (repository/head-SHA/mode/status) the gate performs once it can actually read the artifact.
- **Residual risk:** No currently open PR depends on this gate (all prior `orchestrator/*`/`agent/*` PRs were merged through other means), so the fix is unverified against a live promotion; the next real `orchestrator/*`/`agent/*` preflight success is the first live proof.
- **Prevention rule:** Before trusting a `gh`-CLI-driven workflow step that has no `actions/checkout`, verify it sets `GH_REPO` or passes `--repo` explicitly; "no checkout" and "no repo context" are two different design choices and only the second one is a latent defect.

## ERR-2026-011 — GITHUB_TOKEN-authored automation PRs recur in action_required with zero jobs

- **First observed:** 2026-09-10 (PR #565, head `c730d67e`)
- **Last observed:** 2026-09-11 (PR #575, head `7f6cbf49`)
- **Status:** root_cause_confirmed_external_configuration_fix_pending
- **GitHub references:** #193, PR #565, PR #573 (closed, see below), PR #575
- **User-visible symptom:** The recurring `automation/status-reconcile` reconciliation PR repeatedly shows every required workflow (Golden Verification, Execution Director, CI, Security - TruffleHog, Control Plane, Windows Desktop) as `action_required`, with no jobs or logs, making the automation look like it is failing CI even though no workflow job ever executed.
- **Failing check / evidence:** On PR #575, head `7f6cbf49b7351c37572bb83046ccb872d07f7e9d`, all six required workflow runs created at 2026-09-11T02:53:13Z completed with conclusion `action_required` (run IDs 34556335385, 34556335391, 34556335402, 34556335414, 34556335420, 34556335428) and exposed zero jobs. The same branch's prior head `c730d67ec8ae83455c20fb71367fa3884364b46e` reached `success` only after `triggering_actor` `jweter` manually ran/approved those workflows around 2026-09-11T01:00-02:07Z; a subsequent force-push back to `7f6cbf49` reset the PR into the unapproved `action_required` state again, proving the block recurs on every push rather than being a one-time fluke. The identical pattern was first confirmed on PR #565.
- **Root cause:** `.github/workflows/reconcile-live-status.yml` pushes the `automation/status-reconcile` branch and creates/updates its pull request using the repository `GITHUB_TOKEN` (`github.token`). GitHub intentionally places `pull_request` workflow runs caused by a `GITHUB_TOKEN`-authored push/PR into an approval-required state, so every required check completes as `action_required` before any job is instantiated. This is an automation identity/credential policy interaction, not a Rocksmith product-code or test failure.
- **Affected surfaces:** `.github/workflows/reconcile-live-status.yml` and every PR it opens or updates. No product, timing, mapping, validation, export, or packaging authority is involved.
- **Why prior safeguards missed it:** The workflow was written and exercised assuming `github.token` was sufficient for both pushing and opening a PR; nothing in its own test coverage or prior triage checked whether GitHub's cross-workflow approval policy applies to `GITHUB_TOKEN`-created PRs specifically.
- **Corrective design pattern:** When every `pull_request` workflow on a `github-actions[bot]`-created/updated PR returns `action_required` with zero jobs, classify this as `AUTOMATION_IDENTITY`/`GITHUB_ACTIONS_APPROVAL_POLICY` before attempting any code repair; do not repeatedly rerun or inspect nonexistent job logs.
- **Fix applied:** None yet to the workflow itself. Immediate one-off recovery is a repository user with write access selecting "Approve workflows to run" on the affected PR. The durable fix — authenticating the workflow's git push and `gh pr create`/`update` with a dedicated GitHub App installation token or fine-grained personal access token stored as a repository Actions secret, instead of `github.token` — requires a credential only the repository owner can provision and is not applied by this entry.
- **Verification:** Live GitHub state inspected directly (workflow run list for PR #565 and PR #575, both showing identical `action_required`/zero-job conclusions); no test suite exercises this because it is a GitHub Actions platform policy interaction, not application code.
- **Regression protection:** `engineering/regression-memory.json` records the same finding for automated triage; this entry is the durable, human-readable record.
- **Provenance / invalidation / safety boundary:** CI/automation metadata only; grants no musical, timing, mapping, validation, export, or packaging authority.
- **Residual risk:** Until the workflow stops authenticating with `github.token` for the push/PR-creation step, every new or updated `automation/status-reconcile` PR will recur in `action_required` with zero jobs and either sit unmerged or require a human to manually approve workflow runs on each push.
- **Prevention rule:** A workflow that both writes to a branch and opens/updates its own PR with `github.token` must not be assumed to get ordinary unattended CI; verify whether GitHub's `GITHUB_TOKEN`-created-PR approval policy applies, and if unattended CI is required, provision and use a dedicated App/PAT credential instead. A prior attempt to record this finding (PR #573) was closed by the repository owner because its ledger edit could not be safely reconciled without risking history replacement ("Recreate this documentation change later from a fresh current-main branch with the complete ledger preserved") — edits to this ledger must be strictly additive (append one new dated entry) and must never regenerate or replace the file.

## ERR-2026-012 — A large set of remote feature branches share no git history with `main`

- **First observed:** 2026-09-13, during scheduled-run repository reconnaissance before selecting new work.
- **Status:** monitoring
- **GitHub references:** none yet filed; discovered while checking whether existing branches could be reused per `AGENTS.md`'s "reuse an existing relevant branch when safe" and the automation contract's "do not create a competing implementation for work already actively owned."
- **User-visible symptom:** Roughly a dozen remote branches with real, unmerged-looking commits (e.g. `agent/435-multi-arrangement-tab`, `fix/official-tab-rotation`, `feat/printed-score-review-ui`, `feat/bwv1007-prelude-measure-segmentation`, `agent/desktop-ui-polish-v1`, `claude/blissful-einstein-cp9qa6`, `claude/nice-einstein-1ir286`, `claude/nice-einstein-jyw2jg`, `orchestrator/record-bot-pr-approval-root-cause`) have **no open pull request** and, when compared against `origin/main`, `git diff origin/main...origin/<branch>` fails with `fatal: no merge base`. Each such branch's root commit is its own `Initial commit`/`Add initial project README`, entirely disjoint from `main`'s actual root history. None of their commit messages (checked with `git log origin/main --grep=... -F`) appear anywhere in `main`'s history, so this is not a case of an already-squash-merged branch left undeleted — the work in these branches was genuinely never merged, but it also cannot be `git merge`d or rebased onto current `main` in the ordinary way because the two histories share no common ancestor.
- **Root cause (working hypothesis, not yet confirmed):** Most likely an isolated agent execution environment (e.g. a fresh worktree/container) ran `git init` and committed against a local scratch history instead of branching from a fetched `origin/main`, then force-pushed that disjoint history to a new branch name on `origin`. This is an artifact of how some prior agent sessions were sandboxed, not a defect in this repository's application code, and it is unrelated to ERR-2026-011's `GITHUB_TOKEN` approval-policy finding.
- **Affected surfaces:** Branch/PR hygiene only. No product, timing, mapping, validation, export, or packaging authority is involved, and no code from these orphaned branches has been merged or otherwise trusted.
- **Corrective design pattern:** Before treating a branch with no open PR as reusable "unfinished work," check `git diff origin/main...origin/<branch>` (or `git merge-base`) first. A `fatal: no merge base` result means the branch cannot be reused or fast-forwarded as-is; the underlying idea may still be worth reimplementing fresh against current `main`, but the branch itself is not safely mergeable, and per `AGENTS.md` it must not be deleted without proof it is safely disposable — leave it and note this finding rather than repeatedly re-discovering the same disjoint history.
- **Fix applied:** None; this entry is a durable observation so future scheduled runs do not re-spend a full run investigating the same set of branches. No branch was deleted or force-pushed over.
- **Verification:** `git fetch origin --prune` followed by `git diff --stat origin/main...origin/<branch>` for each named branch (all reported `fatal: no merge base`), and `git log origin/main --oneline --grep="<branch's own commit subject>" -F` for a sample of branch commit messages (all returned no matches in `main`).
- **Regression protection:** None needed; this is a one-time reconnaissance finding, not a repeatable test condition.
- **Provenance / invalidation / safety boundary:** Git history/branch hygiene metadata only; grants no musical, timing, mapping, validation, export, or packaging authority.
- **Residual risk:** A future scheduled run may still waste time re-investigating one of these branches if it does not check for a merge base first; this entry and the prevention rule above are the mitigation until the branches are either explicitly reimplemented against current `main` or a human decides they are safe to delete.
- **Prevention rule:** Always confirm a candidate "unfinished work" branch shares history with `main` (`git merge-base` succeeds) before attempting to reuse, rebase, or merge it; a disjoint-history branch is not "existing work that can be completed" and should be treated as reference material for a fresh reimplementation at most, never merged directly.

## Maintenance rules

- Cross-link recurring defects to GitHub issue #193 or a more specific root-cause issue.
- Prefer one root-cause entry over many symptom-only entries when failures share the same mechanism.
- Update an existing entry when new evidence changes the understood root cause or prevention rule.
- Do not rewrite history to make an earlier diagnosis look correct; preserve the evolution of the evidence in GitHub and summarize the current best-supported root cause here.
- Product Reality and major milestone issue sweeps should consult this ledger for unresolved sibling failure patterns.

## ERR-2026-013 — Full-band pYIN Bass guesses cannot qualify score/audio alignment

- **First observed:** 2026-11-21, after the first genuinely automatic periodic Rocksmith worker run.
- **Last observed:** 2026-11-21.
- **Status:** active; worker diagnostic mitigation proposed on agent/unattended-audio-evidence-triage-20261121, independent bass transcription not solved.
- **GitHub references:** #612 and Product Reality timing/recording verification.
- **User-visible symptom:** Six recent projects all report `REVIEW_REQUIRED` indefinitely despite hundreds of apparent Bass note detections.
- **Failing check / evidence:** On Azathoth's verified build `344a8f53`, all six source timing qualifiers compared 64 symbolic events against hundreds of pYIN Bass note candidates but found zero with sufficient confidence, pitch reliability and onset confidence. Every `analysis/bass_raw.json` was derived from full-mix `audio/normalized.wav`; none had a separated `stems/bass.wav`. Six project variants represent only four different recording SHA-256 identities.
- **Mechanism:** pYIN estimates a single F0 from a polyphonic mix with bass, guitars and percussion. It emits timestamps/pitches without sufficient confidence to establish a Bass-onset correspondence, so numerical note count is not evidence quality. All six show maximal note confidence below 0.60 and negligible pitch confidence; the independent qualifier correctly rejects them.
- **Failed alternative hypothesis:** Private 12-second ffmpeg+librosa comparison on a single recording found 20 original / 33 with 230-Hz low-pass / 29 with 430-Hz low-frequency filtering candidate events, but **zero strong notes** for all three. Filtering cannot be declared a substitute for isolated bass evidence.
- **Why existing safeguards missed diagnosis:** The worker already preserved `insufficient_evidence` but gave the same status for missing transcriptions, an unqualified full mix and intrinsically ambiguous score onset matching. It did not expose an explicit next automatable dependency or count distinct recording inputs among multiple project versions.
- **Corrective design pattern:** Preserve exact original thresholds and per-score qualification; report sanitized stable `audio_evidence_gap` and `next_automation_dependency` codes and unique recording counts. Never count an unqualified note as trustworthy, never infer a global phase correction from zero qualified events, and never ask the user to manually retest a deterministic audio-evidence shortfall.
- **Verification:** Local synthetic regression tests on isolated Windows Python runtime: 35 passed for source-quality triage plus existing worker behavior. Full CI and independent review needed before any merge.
- **Next independent capability:** Verify a locally licensed, RAM/disk-admissible bass separation runtime and separately hash-bound, clock-preserving stem transcription, then test real song/drift negatives against the same strict source timing qualifier. No model or source separation was launched by the diagnostic code, and no gameplay truth claimed.
- **Prevention rule:** Prioritize source-confidence/provenance evidence before tuning score-to-audio alignment. Never lower strict thresholds to force an automated PASS and never treat duplicate project variants as independent audio recordings.



## ERR-2026-014 — Alignment method v7 invalidated pre-promotion score preview fixture

- **First observed:** 2026-11-21 in PR #805 Python CI (run 44966371023, before final fixes).
- **Status:** fixed in branch; exact-head CI/Windows bridge pending verification.
- **GitHub references:** PR #805; timing Product Reality #455; 62-slice delivery #796.
- **Symptom:** Three preview tests failed when a v6 `SharedTimeline` test fixture was materialized as the new v7-only `AlignmentReport`, throwing a Pydantic method literal validation error.
- **Root cause:** The v7 repeated-riff trust gate intentionally invalidates pre-v7 alignment authority, but an unrelated pre-promotion preview fixture hardcoded the old method string. At the same time, the preview and promoted per-role adapters were not yet copying the new explicit phase-ambiguity status from `SharedTimeline`.
- **Correction:** Use `CURRENT_ALIGNMENT_METHOD` in the synthetic preview fixture; propagate `phase_ambiguous` and `equivalent_phase_candidates` through both pre-promotion `score_preview._alignment_from_candidate` and promoted `shared_timeline.alignment_for_role`. Add Bass/Lead/Rhythm round-trip regression and independent repeated-phrase promotion-denial regression.
- **Why this matters:** Merely changing a version constant cannot establish safe stale-state invalidation if role-specific adapters lose new trust fields or existing fixtures bypass the intended currentness contract.
- **Prevention rule:** When bumping an evidence schema/method version, enumerate every adapter that rebuilds the model, replace hardcoded fixture strings with authoritative constants, and assert new risk fields survive each role-specific transformation. Do not downgrade v7 to accept stale v6 evidence to make tests pass.
- **Remaining evidence:** Exact final-head CI and reviewer findings must pass before declaring this guard merged or user-level musical correctness.


## ERR-2026-015 — Merged PR receipts must not validate rewritten slice semantics

- **First observed:** 2026-11-21 during PR #806 independent P2 code review (GitHub thread on `slice_readiness.py`).
- **Status:** Fix committed; final exact-head verification and reviewer resolution pending.
- **Tracking:** [PR #806](https://github.com/jweter/rocksmith-cdlc-generator/pull/806), issue #796 slice 56.
- **Failure:** A previously checked prerequisite could keep its valid old merged PR/CI receipt even after issue #796's title or acceptance criteria changed. A same-ID rewrite could then unlock dependent work which the original PR never actually proved. Re-reading the issue at the end of an API inspection would only catch concurrent edits, not edits made *before* the inspection.
- **Root cause:** The first receipt contract bound `slice_number`, `PR number`, original head SHA, merge SHA and exact-head CI, but omitted the *semantic meaning* of the task that the PR satisfied.
- **Fix:** Store a reviewed SHA-256 for each checked item's padded ID, title and exact acceptance statement. Also record one Git-blob fingerprint over the full ordered 62-item ID/group/title/acceptance graph, deliberately excluding checkbox status. Refuse scheduling on any changed canonical task meaning or group until the reviewed dependency model is updated. Fail closed even if the old PR remains merged with green CI; checkbox progress alone does not invalidate the reviewed queue graph. New regressions mutate a checked prerequisite's acceptance without clearing its checkbox and verify that all readiness is withheld.
- **Privacy/authority:** No private song content or paths enter receipts. The new proof guards *eligibility to begin engineering*, not automatic model execution, authority to release CDLC, or gameplay PASS.
- **Prevention:** Every machine-used work receipt must bind both its producing code/CI and the reviewed specification it proves. Treat changed acceptance language as stale evidence requiring independent re-review, not merely a documentation change.
- **Additional exact-head Python CI regression:** The synthetic director integration test initially mixed the real on-disk, issue-bound graph fingerprint with a deliberately synthetic issue body. The resulting correct production HOLD made the test falsely expect EXECUTE. The test now injects a matching synthetic-reviewed contract into the director's source loader and also exercises an issue-edit race with that coherent fixture; the production semantic-fingerprint gate remains unchanged. Root cause was test fixture provenance mismatch, not a reason to relax the safety guard.

- **ERR-2026-016 — Merge-receipt projection lag versus canonical task checkboxes (2026-11-21).** After merged PRs #806, #807 and #808 the canonical issue #796 had 19 checked tasks but `engineering/rocksmith-slice-dependencies.json` retained 16 acceptance-bound receipts. **Cause:** marking the public checklist and updating the Git-tracked prerequisite receipt projection were separately performed; neither automatically supplied the independent original-head/merge/CI review proof. **Impact:** slices 10, 20, 56 were correctly reported `CHECKED_BUT_MERGE_UNVERIFIED`; the otherwise-admissible host-concurrency engineering slice #21 could not use completed #10 as proof. **Repair:** independently verify GitHub merged status, original PR head, final merge SHA, and exact-head successful Python + Windows/PSARC + Windows Desktop checks, then append the three original-acceptance SHA-256 receipts. Keep the full queue revision invariant unchanged. **Prevention:** regressions pin each source PR's exact head, merge and specification; individually broken per-PR Windows/pending checks, head or merge must block its own dependency; edited acceptance must fail closed. **Scope:** only advisory scheduler readiness, not model execution, Windows offline security, musical accuracy or gameplay acceptance.

- **ERR-2026-017 — Preflight-to-model-launch RAM-pressure race (2026-11-21).** The earlier optional Bass source-separator gate inspected available physical RAM before the private output staging and command construction. Concurrent unrelated workloads could reduce RAM after that snapshot, while the actual subprocess would still start from stale ADMITTED evidence. **Fix:** a bounded three-sample physical-memory stability window is enforced inside the actual `AudioSeparatorBassStemSeparator.separate` spawn boundary, with a 0.5-GiB transient host-concurrency margin beyond the existing 7-GiB admission floor. Missing sensors, below-threshold observations and malformed values fail closed without launching a process. **Regression:** synthetic 9->6.5 GiB and late-sample 7.4 GiB drops, sensor exceptions/NaN/bool/text, zero permitted subprocess invocations under memory pressure. **Limits:** this is not ongoing memory enforcement, a model-RAM benchmark, GPU proof, Windows Home offline network isolation, or actual Bass musical evidence.

- **ERR-2026-016 continuation — receipt maintained after next canonical merge.** Following verified merge #810, immediately add slice 21's original PR head `80805fcb6f414c2d796b0be04f877c169adcb9ec`, resulting commit `2fd6bd3c1451d28bbadf61d2231f84457dde5ad1`, current original-acceptance SHA-256, and exact-head successful Windows/Python/Desktop proof to the production 62-slice receipt contract. Update independent targeted missing/pending/forged CI regressions and safe next-slice selection rather than leaving the already-known drift class uncorrected.

- **ERR-2026-018 — Percussion-only or silent content could inherit Bass stem trust from metadata (2026-11-21).** A hash-bound Bass receipt, matching master PCM geometry, original-clock alignment and non-cloned waveform constitute necessary provenance constraints but do **not** prove the instrument in the candidate is Bass. An unrelated transient-only/silent file could be paired with fabricated pYIN notes reporting perfect pitch/timing/confidence and still reach the note-qualification gate as a verified stem if older gates independently passed. **Bounded repair:** production `is_verified_bass_stem_transcription` now calls a read-only, distributed-sample DC-corrected 10-ms continuity negative control on the actual stem, denying a trusted source for obvious silence/isolated percussion cases. **Regression:** original synthesized silence, DC, pitched low kick, unrelated high drum, denser short kicks, true sustained Bass control, inverted stereo, truncated WAV, and fake-perfect transcript with all earlier trust checks forced green. **Staleness:** reconciliation v7 invalidates cached v6 trusted charts. **Limit:** not a positive instrument classifier; steady unrelated audio and real short Bass remain review-lane uncertainties. No model execution, two-measure timing resolution, or gameplay claim.

- **ERR-2026-019 — Octave-dominant non-Bass partials produce a misleading E1 diagnostic (2026-11-21).** Existing stationary-window Goertzel diagnostic scored the sum of E1/E2/E3/E4 harmonic magnitudes against semitone/octave rivals; a weak E1 fundamental could borrow higher partial energy to beat the 1.75x competitor margin and 0.25 root-to-top threshold. **Bounded repair:** independently require E1 first-harmonic magnitude / E2 second-harmonic magnitude >=0.55 in both windows. Publish only a sanitized `octave_leakage_negative` and minimum ratio diagnostic; ambiguous is a veto, never a note pitch or instrument proof. **Regression:** original synthetic E1/E2/E3/E4 negative amplitudes 1500/5000/4000/2000 and rooted E1 control 3600/5000/2000/1400. **Limit:** heuristic ratio without measured real-song calibration; spectral partials do not prove instrument identity, model rights, original timing or gameplay. Related PR also fixes post-merge slice 28 evidence-receipt lag (ERR-2026-016).

- **ERR-2026-019 production-admission follow-through.** Diagnostic-only octave ambiguity cannot prevent the actual note trust path from accepting a fake-perfect E1 pYIN match over non-Bass E2. The same slice-31 PR also injects a separate strong-octave-negative veto into the actual verified-stem `reconcile_project_bass` / `reconcile_bass_sources` promotion boundary. Two disjoint 320-ms windows require strong local E2 support and >=8:1 octave/root amplitude before adding `OCTAVE_LEAKAGE_NEGATIVE`; unavailable source adds `OCTAVE_SCREEN_UNAVAILABLE`. Expensive PCM inspection runs only for otherwise fully qualified matched candidates, cannot bypass unverified source gates, and does not establish a positive Bass instrument. Version v8 invalidates old v7 trusted charts. Synthetically forged perfect-confidence E1 over only E2 remains symbolic-unverified. The 0.55 advisory harmonic plausibility threshold and 8:1 production negative threshold serve different purposes and are not interchangeable; real source accuracy and short-note behavior remain unproven.

- **ERR-2026-020 — pYIN-estimated note time lacked an independent local PCM attack check (2026-11-22).** A Bass `NoteEvent` carries self-reported `pitch_confidence` and `timing_confidence`; even when correctly evaluated at a detected Librosa onset peak instead of its backtracked energy minimum, a fabricated or inaccurate 100%-confident note can match score pitch and onset on paper without an independent attack in the current verified Bass stem. **Bounded repair:** production `reconcile_project_bass` injects local 270-ms DC-removed RMS onset contrast analysis into matched notes that passed all older source, pitch, alignment and octave gates. A 30-ms sustained post-attack signal must exceed 250 RMS per 10ms bin, jump 200 RMS and rise 2.5x against the previous 30ms in a measured 10ms bin starting before +80ms of backtracked onset; exact-border and +85/+89ms attacks conservatively remain review-only. No measurable attack, insufficient local context or missing PCM forces review; new `qualification_reasons/observations/thresholds` explain why. **Regression:** original synthetic Bass onsets at 0/+40ms, steady tonal Bass with no onset, DC/silence, isolated impulse and a +3ms click straddling two bins over steady E1, stereo inversion, +85/+89/+110ms late onset, missing/truncated audio, fake-perfect pYIN metadata, untrusted source and octave negative shortcuts. **Stale:** reconciliation v9 invalidates v8 cached trusted charts. **Limits:** transients aren't instrument identity, real Bass attack sensitivity and real-song false-positive rates unmeasured, original two-bar timing and gameplay unproven.
