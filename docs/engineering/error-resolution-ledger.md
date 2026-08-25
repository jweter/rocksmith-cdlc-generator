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
- **GitHub references:** #193 and the linked status-consistency repair series
- **User-visible symptom:** A merged feature can leave a post-merge automated review finding unresolved on `main`; PR #404 left contradictory automation state, and PR #418 could fold a tie onto an adjacent lookalike from another selected composition track.
- **Failing check / evidence:** Post-merge Codex review comments on PRs #404 and #418 identified, respectively, contradictory authoritative status and lost per-note composition origin at the reviewed tie-fold boundary.
- **Root cause:** Merge completion was treated as safe from workflow results without independently reconciling review timing/state. PR #404's review arrived asynchronously around the merge, while PR #418 still had a material unresolved thread when it merged. The status contract also validated required fields without validating consistency between the active change and continuation pointer.
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

## Maintenance rules

- Cross-link recurring defects to GitHub issue #193 or a more specific root-cause issue.
- Prefer one root-cause entry over many symptom-only entries when failures share the same mechanism.
- Update an existing entry when new evidence changes the understood root cause or prevention rule.
- Do not rewrite history to make an earlier diagnosis look correct; preserve the evolution of the evidence in GitHub and summarize the current best-supported root cause here.
- Product Reality and major milestone issue sweeps should consult this ledger for unresolved sibling failure patterns.
