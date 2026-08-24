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
- **Last observed:** 2026-08-24
- **Status:** monitoring
- **GitHub references:** #193, PR #404, PR #405, and the focused single-authority follow-up PR
- **User-visible symptom:** A merged feature can leave a post-merge automated review finding unresolved on `main`; in PR #404, `next_continuation` described the new Review Queue slice while `active_change` still identified already-merged PR #403 as pending.
- **Failing check / evidence:** Post-merge Codex review comment on PR #404 identified contradictory authoritative automation state.
- **Root cause:** Fresh CI completed and the PR merged before the asynchronous review result arrived; the status contract validated required fields but did not validate consistency between the active change and continuation pointer.
- **Affected surfaces:** Scheduled-run selection, durable project status, and any future PR whose asynchronous review finishes after CI/merge.
- **Why prior safeguards missed it:** The existing readiness check verified policy and workflow declarations but treated `active_change` and `next_continuation` as independent narrative fields.
- **Corrective design pattern:** Keep exactly one structured active-PR authority (`active_change.pr_number`) and reject legacy duplicate pointers anywhere else in the status contract.
- **Fix applied:** PR #405 cleared the stale active change and added an initial two-field guard. Its late review exposed a third pointer, so the follow-up removes both legacy pointers and makes readiness reject their reintroduction.
- **Verification:** Focused tests accept one valid `active_change.pr_number` and require deterministic readiness failures when either legacy pointer is reintroduced.
- **Regression protection:** `tests/test_automation_readiness.py` covers the sole valid active-PR source plus forbidden continuation and verified-state pointers.
- **Provenance / invalidation / safety boundary:** This changes automation metadata only; it does not alter musical, source, mapping, validation, export, or packaging authority.
- **Residual risk:** Asynchronous review findings can still arrive after merge; every run must continue checking recently merged PRs and repair substantive findings on a new branch.
- **Prevention rule:** Never encode active PR identity in more than one structured field; narrative history may mention PRs, but automation selects only from `active_change`.

## Maintenance rules

- Cross-link recurring defects to GitHub issue #193 or a more specific root-cause issue.
- Prefer one root-cause entry over many symptom-only entries when failures share the same mechanism.
- Update an existing entry when new evidence changes the understood root cause or prevention rule.
- Do not rewrite history to make an earlier diagnosis look correct; preserve the evolution of the evidence in GitHub and summarize the current best-supported root cause here.
- Product Reality and major milestone issue sweeps should consult this ledger for unresolved sibling failure patterns.
