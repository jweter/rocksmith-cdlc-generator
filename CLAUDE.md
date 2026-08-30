# CLAUDE.md

## Repository Role

This repository contains the Rocksmith 2014 custom DLC generation project.

Follow the current repository roadmap, architecture, tests, issues, PRs, and documented design decisions.

## Required Agent Context

Before selecting or implementing substantial work, read:

1. `AGENTS.md` — autonomous development constitution and authority order.
2. `PROJECT_PLAN.md` — canonical product roadmap.
3. `docs/project-status.yaml` — current continuity snapshot, reconciled against live repository state.
4. `docs/agent-development-policy.md` — detailed autonomous workflow and Product Reality rules.
5. `docs/INDUSTRY_REALITY_CHECK.md` — the current repo-specific gap analysis versus dependable music-authoring/desktop-tool expectations.

Treat `docs/INDUSTRY_REALITY_CHECK.md` as a durable quality-gap baseline, not as a replacement for verified repository state, Product Reality evidence, or `PROJECT_PLAN.md`. Prefer roadmap-compatible work that closes a documented quality gap when priorities are otherwise comparable. Do not declare a gap closed merely because code exists or CI passes when the report calls for representative song evidence, EOF differential parity, packaged Windows behavior, arrangement symmetry, user-workflow evidence, or actual Rocksmith playability. Update the assessment when major verified capability materially changes its conclusions.

## Engineering Priorities

Prefer, in order:

1. Fix failing existing PRs or tests.
2. Complete unfinished work.
3. Fix verified timing, arrangement, import, generation, or workflow defects.
4. Implement the highest-value authorized roadmap slice.
5. Refactor or clean up only when it supports current work.

Prefer small, coherent, reversible changes.

## Hard Boundaries

Never modify:
- the user's live Rocksmith installation
- NoCableLauncher

Never commit:
- commercial audio
- commercial DLC
- Ubisoft-derived restricted material
- private/generated source material that should remain gitignored

Preserve:
- Bass as an independent first-class arrangement
- Lead Guitar as an independent first-class arrangement
- Rhythm Guitar as an independent first-class arrangement
- human review gates where musical interpretation, timing, arrangement, provenance, or source acceptance is uncertain

New development PRs require fresh independent CI before merging.

## Accuracy

Do not invent timing, note, arrangement, or source correctness.

When reference material or known-good external behavior contradicts generated output, investigate the underlying cause rather than hiding the discrepancy.

Prefer regression tests for confirmed bugs.

## Verification

Never claim a test, fix, PR, merge, generated arrangement, or workflow succeeded unless verified.

Do not merge failed, pending, conflicted, blocked, or materially uncertain work.

Run targeted tests appropriate to the change.

## Scope

Work only on files relevant to the selected task.

Do not perform unrelated cleanup.

Read only the documentation, code, logs, and tests required for the current task.

## Human Decisions

Make routine engineering decisions autonomously.

Ask Jeremy only for:
- fundamental product-direction changes
- major unauthorized architecture changes
- paid services
- license changes
- destructive migrations
- credential problems
- publishing/release authorization
- irreversible actions
- materially ambiguous product outcomes
