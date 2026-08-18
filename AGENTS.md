# Rocksmith CDLC Generator — Autonomous Development Constitution

This repository is designed for both human development and scheduled autonomous engineering work. Automated agents must treat the current repository state and the documents named below as authoritative and must never rely on conversational memory when repository evidence is available.

## Authority order

When sources disagree, use this order:

1. Verified current repository state: code, tests, CI, open PRs/issues, and actual tool behavior.
2. `PROJECT_PLAN.md` — canonical product roadmap and product direction.
3. `docs/project-status.yaml` — current continuity snapshot; this file must be kept fresh whenever work changes project state.
4. `docs/agent-development-policy.md` — autonomous engineering workflow, merge policy, safety rules, and escalation boundaries.
5. `docs/PRODUCT_VISION.md` and current architecture/design/ADR documents relevant to the work.
6. Historical planning and adaptation documents.
7. Conversation memory or assumptions.

If a lower-authority document conflicts with higher-authority repository evidence, update the stale document in the same PR when practical.

## Product invariants

- Bass, Lead Guitar, and Rhythm Guitar are equally important first-class arrangements. Development may use whichever path is technically easiest to prove a shared capability, but no arrangement is a lesser product target.
- The intended end state is one song project that can produce reviewed playable Bass + Lead + Rhythm arrangements from one recording plus a complete structured score when available.
- The GUI is the primary product. The CLI is the deterministic engine/debugging surface.
- Preserve explicit provenance, confidence, human-review authority, and stale-state invalidation.
- Never invent unresolved guitar string/fret positions, techniques, timing authority, source rights, or package readiness.
- Never modify the live Rocksmith installation or NoCableLauncher.
- Packaging remains validation-gated.

## Repository content boundary

Default to keeping commercial/private source material out of Git. Do not commit commercial audio, copyrighted score/tab files supplied for personal use, private PSARC/CDLC packages, CFSM exports, Steam profiles/save data, extracted Ubisoft-derived assets, generated private project workspaces, or copyrighted stems.

Safe committed fixtures should be original, synthetic, public-domain, explicitly licensed for redistribution, or otherwise clearly redistributable. Small metadata/provenance records may be committed when they do not embed restricted source content and project policy permits it.

When uncertain whether material is safe to commit, keep it local/private and escalate rather than guessing.

## Hourly autonomous run

At the start of every scheduled run:

1. Inspect open PRs and classify each as GREEN, FAILED, PENDING, CONFLICTED, BLOCKED, or UNCERTAIN.
2. Inspect required CI/checks, mergeability, and blocking review state.
3. Read `PROJECT_PLAN.md`, `docs/project-status.yaml`, and relevant current design/ADR documents before starting new work.
4. Inspect relevant open issues, especially Product Reality findings and recurring defect patterns.
5. Reconcile `docs/project-status.yaml` with verified repository reality; correct stale status in the same PR when work changes it.

Existing broken or merge-ready work takes priority over starting new roadmap work.

### GREEN PR

Merge only when all required checks are present and successful, mergeability is resolved, no blocking review/comment remains, and there is no material correctness, safety, licensing, provenance, or product-policy concern. Verify the merge succeeded.

### FAILED PR

Inspect the actual failure and logs, identify the root cause from evidence, make the smallest safe fix on the existing branch, add/update regression protection when appropriate, push, and leave the PR for fresh CI. Do not claim success until fresh evidence supports it.

Significant or recurring failures must be recorded both in the relevant GitHub issue/PR and in `docs/engineering/error-resolution-ledger.md`.

### PENDING PR

Do not merge and do not duplicate its work.

### CONFLICTED / BLOCKED / UNCERTAIN PR

Investigate and resolve routine engineering problems when clearly safe. Never force a merge to create progress.

## New roadmap development

When no higher-priority existing work needs action:

1. Select the highest-value currently authorized slice from the current milestone.
2. Prefer completing the active milestone before starting a later one.
3. Implement one small, coherent, reviewable slice.
4. Add/update tests and documentation.
5. Update `docs/project-status.yaml` in the same PR so the next run has a truthful continuation point.
6. Create a focused branch and PR.
7. Stop and leave the newly opened PR for fresh independent CI.

At most one substantial new roadmap implementation should be started for this repository in a single hourly run.

## Documentation freshness

Documentation is part of the product state, not optional cleanup. Any PR that changes behavior, architecture, milestone completion, safety boundaries, or the next continuation point must update the relevant authoritative documents in the same PR.

`docs/project-status.yaml` must never be treated as write-once metadata. Every autonomous run must verify it against repository reality, and any run that changes reality must update it.

Routine implementation-level architecture decisions may receive new ADRs autonomously. Major product/architecture shifts require human direction.

## Human escalation

Ask Jeremy only for decisions that materially change product direction or authority, including:

- fundamental product-direction change;
- major architecture change not supported by current roadmap/docs;
- new paid service or meaningful recurring cost;
- license change;
- destructive or irreversible migration;
- security/privacy boundary change;
- credential/secret problem requiring human action;
- publication/release/distribution authorization;
- genuinely ambiguous requirements with materially different product outcomes.

Do not interrupt for routine coding judgments supported by repository evidence.

## Truthfulness

Never fabricate repository access, files, branches, commits, PRs, issues, test results, CI state, mergeability, errors, fixes, or project progress. Passing CI proves only what the checks actually exercise; it does not replace the Product Reality Gate.
