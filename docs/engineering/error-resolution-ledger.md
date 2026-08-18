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

## Maintenance rules

- Cross-link recurring defects to GitHub issue #193 or a more specific root-cause issue.
- Prefer one root-cause entry over many symptom-only entries when failures share the same mechanism.
- Update an existing entry when new evidence changes the understood root cause or prevention rule.
- Do not rewrite history to make an earlier diagnosis look correct; preserve the evolution of the evidence in GitHub and summarize the current best-supported root cause here.
- Product Reality and major milestone issue sweeps should consult this ledger for unresolved sibling failure patterns.
