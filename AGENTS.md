# Rocksmith CDLC Generator — Autonomous Development Constitution

This repository supports scheduled autonomous engineering. Agents must reload context from current repository evidence rather than rely on conversation memory.

## Authority order

When sources disagree, use this order:

1. Verified current repository state: code, tests, CI, open PRs/issues, and actual tool behavior.
2. `PROJECT_PLAN.md` — canonical product roadmap and direction.
3. `docs/project-status.yaml` — current continuity snapshot; keep it fresh whenever work changes project state.
4. `docs/agent-development-policy.md` — autonomous workflow, merge policy, safety rules, and escalation boundaries.
5. `docs/PRODUCT_VISION.md` plus current architecture/design/ADR documents relevant to the work.
6. Historical planning/adaptation documents.
7. Conversation memory or assumptions.

If lower-authority documentation conflicts with higher-authority repository evidence, update the stale documentation in the same PR when practical.

## Product invariants

- Bass, Lead Guitar, and Rhythm Guitar are equally important first-class arrangements. A technically easier path may prove a shared capability first, but no arrangement is a lesser product target.
- The intended end state is one song project producing reviewed playable Bass + Lead + Rhythm arrangements from one recording plus a complete structured score when available.
- The GUI is the primary product. The CLI remains the deterministic engine/debugging surface.
- Preserve provenance, confidence, human-review authority, and stale-state invalidation.
- Never invent unresolved guitar string/fret positions, techniques, timing authority, source rights, or package readiness.
- Never modify the live Rocksmith installation or NoCableLauncher.
- Packaging remains validation-gated.

## Mature reference implementation policy

Issue #414 establishes Editor on Fire (EOF) and the mature Rocksmith authoring ecosystem as first-class engineering references.

Before implementing or materially changing deterministic Guitar Pro/Rocksmith domain logic, inspect the relevant mature reference implementation first. Start with `raynebc/editor-on-fire` for GP/beat/note/chord/FHP/phrase/Rocksmith authoring semantics, then inspect high-value forks or Rocksmith Custom Song Toolkit/DDC where they are more relevant.

For affected PRs:

1. State which mature reference path/behavior was inspected, or state that no relevant mature behavior was found.
2. Prefer tested parity with proven behavior over inventing a new rule.
3. Port/adapt BSD-licensed EOF code or algorithms when that is the smallest correct solution, with required attribution and upstream path/commit provenance for substantial reuse.
4. Review file/subtree licenses before copying third-party or adjacent-tool code; do not assume EOF's root license applies to vendored dependencies or other projects.
5. Preserve this repository's stronger provenance, human-review, stale-authority, validation and safety boundaries even when the reference tool is more permissive/manual.
6. When intentionally diverging, document the reference behavior and why this product should differ.
7. Add differential/oracle regression coverage for adopted behavior whenever practical.

Use `docs/eof-reference-parity-program.md`, `docs/eof-subsystem-parity-matrix.md`, and `docs/eof-upstream-fork-inventory.md` as the durable working record. EOF parity is a correctness floor, not a requirement to copy its GUI or mutable editor architecture.

## Repository content boundary

Default to keeping commercial/private source material out of Git. Do not commit commercial audio, copyrighted score/tab files supplied for personal use, private PSARC/CDLC packages, CFSM exports, Steam profiles/save data, extracted Ubisoft-derived assets, generated private project workspaces, or copyrighted stems.

Safe committed fixtures should be original, synthetic, public-domain, explicitly redistributable, or otherwise clearly licensed for repository use. Small metadata/provenance records may be committed when they do not embed restricted source content and project policy permits it.

When uncertain, keep the material local/private and escalate rather than guessing.

## Scheduled-run contract

At the beginning of each hourly run:

1. Inspect all open PRs and classify each as GREEN, FAILED, PENDING, CONFLICTED, BLOCKED, or UNCERTAIN.
2. Inspect required CI/checks, mergeability, and blocking review state.
3. Read `PROJECT_PLAN.md`, `docs/project-status.yaml`, and the design/ADR documents relevant to current work.
4. Inspect relevant open issues, especially Product Reality findings and recurring defect patterns.
5. Reconcile `docs/project-status.yaml` against verified repository reality.

Existing broken or merge-ready work takes priority over starting new roadmap work.

### GREEN

Merge only when all required checks are present and successful, mergeability is resolved, no blocking review/comment remains, and there is no material correctness, safety, licensing, provenance, or product-policy concern. Verify the merge succeeded.

### FAILED

Inspect the actual failure/logs, determine the root cause from evidence, make the smallest safe correction on the existing branch, add/update regression protection when appropriate, push, and leave the PR for fresh CI. Significant or recurring failures must be captured both in the relevant GitHub issue/PR and in `docs/engineering/error-resolution-ledger.md`.

### PENDING

Do not merge and do not duplicate its work.

### CONFLICTED / BLOCKED / UNCERTAIN

Investigate and resolve routine engineering problems when clearly safe. Never force merge merely to create progress.

## New roadmap work

When no higher-priority existing work needs action:

1. Select the highest-value authorized slice from the current milestone.
2. Prefer completing the active milestone before starting later work.
3. For deterministic Guitar Pro/Rocksmith domain behavior, perform the mature-reference check required by issue #414 before designing new semantics.
4. Implement one small, coherent, reviewable slice.
5. Add/update tests and documentation.
6. Update `docs/project-status.yaml` in the same PR.
7. Open a focused PR and leave it for fresh independent CI.

At most one substantial new roadmap implementation should be started for this repository per hourly run.

## Documentation freshness

Documentation is product state, not optional cleanup. PRs that change behavior, architecture, milestone completion, safety boundaries, or the continuation point must update the relevant authoritative documents in the same PR.

Every scheduled run must verify `docs/project-status.yaml`; any run that changes reality must update it. Routine implementation-level architecture decisions may receive ADRs autonomously. Major architecture or product-direction changes require human direction.

## Human escalation

Ask Jeremy only for material decisions such as fundamental product direction, major architecture not authorized by current docs, new paid services or meaningful recurring cost, license changes, destructive/irreversible migrations, security/privacy boundary changes, credentials/secrets requiring human action, publication/release/distribution authorization, or genuinely ambiguous requirements with materially different outcomes.

Do not interrupt for routine coding judgments supported by repository evidence.

## Truthfulness

Never fabricate repository state, branches, commits, PRs, issues, test results, CI state, mergeability, errors, fixes, or progress. Passing CI proves only what the checks exercise; it does not replace the Product Reality Gate.
