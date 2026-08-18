# Agent Development Policy

This policy defines the repository-local operating contract for scheduled autonomous development. `AGENTS.md` is the short constitution; this file gives the detailed execution rules.

## Intent

Autonomous work should move the project from verified current state toward the current roadmap's ideal state while preserving product, safety, provenance, licensing, and human-review boundaries.

The loop is:

```text
verified current state
  -> explicit current milestone / continuation point
  -> highest-value authorized action
  -> implementation
  -> tests + evidence
  -> PR + independent CI
  -> merge only when verified green
  -> update status / engineering memory
  -> improved current state
```

## Repository isolation

This repository is the Rocksmith CDLC Generator project. Do not import Knowledge Engine, Everward, or unrelated project requirements, terminology, architecture, priorities, or implementation assumptions.

## Source of truth and freshness

Use the authority order in `AGENTS.md`. Repository evidence outranks historical plans and conversation memory. If an implementation or merged PR makes an authoritative document stale, updating that document is part of the work, not deferred cleanup.

`docs/project-status.yaml` is a continuity cache. It must be verified at the start of every scheduled run and updated whenever the run changes project reality. It never overrides code, CI, PR/issue state, or `PROJECT_PLAN.md`.

## Arrangement parity

Bass, Lead Guitar, and Rhythm Guitar are equal product targets. Architectural work should generalize across arrangement types when the capability is shared. It is acceptable to prove a technically difficult mechanism on one arrangement first when doing so reduces risk, but the roadmap and final acceptance must preserve all three.

Do not regress shared architecture into Bass-only assumptions merely because Bass was historically the first proving path.

## PR state machine

Existing work takes priority over new work.

### GREEN

A PR may be merged automatically only when all of the following are verified:

- all required checks are present;
- every required check succeeded;
- the PR head SHA examined is the SHA being merged;
- mergeability is resolved and the PR is mergeable;
- required review conditions are satisfied;
- no unresolved blocking review thread/comment remains;
- no material correctness, security, safety, licensing, provenance, privacy, or product-policy concern remains.

After merge, verify GitHub reports the merge succeeded.

### FAILED

When CI fails:

1. Inspect the actual failed workflow/job/check and logs.
2. Identify the first meaningful failure rather than patching downstream symptoms.
3. Determine root cause from evidence.
4. Reproduce locally when practical.
5. Make the smallest safe correction on the existing PR branch.
6. Add/update regression tests where the defect class warrants protection.
7. Run targeted checks.
8. Push the correction.
9. Leave the PR for fresh CI.
10. Do not call the failure fixed until fresh evidence supports the claim.

If the failure is significant, recurring, or reveals a reusable engineering lesson, update both the relevant GitHub issue/PR and `docs/engineering/error-resolution-ledger.md`.

### PENDING

Do not merge. Do not duplicate the work. Avoid dependent changes that assume the pending PR has merged unless the repository has an explicit stacked-PR plan.

### CONFLICTED / BLOCKED / UNCERTAIN

Investigate. Resolve routine, evidence-supported conflicts when safe. Never force merge to manufacture progress.

## New development selection

If no higher-priority PR needs action, select work in this order:

1. P0 safety, corruption, data-loss, or major correctness problem.
2. P1 failed existing PR that can be safely repaired.
3. P2 verified green merge-ready PR.
4. P3 blocking review feedback or conflict.
5. P4 incomplete current milestone / already-started work.
6. P5 highest-value authorized roadmap slice.
7. P6 refactoring/optimization/docs/technical debt without a current blocker.

Within equal priority, unblock dependencies first, then favor older blockers, higher user/product value, and the smallest coherent implementation.

At most one substantial new roadmap implementation may be started in this repository during one hourly run.

## Development workflow

For a new slice:

1. Read the current milestone in `PROJECT_PLAN.md`.
2. Verify `docs/project-status.yaml` and relevant issues.
3. Read relevant design/ADR files.
4. Define a small falsifiable completion target.
5. Implement only that target.
6. Add/update deterministic tests and representative integration/UI checks as appropriate.
7. Update documentation and status in the same branch.
8. Open one focused PR.
9. Stop and leave the new PR for independent CI; do not merge it in the same run solely because local tests passed.

## Product Reality discipline

CI is necessary but not sufficient. Interactive/product claims require Product Reality evidence when the roadmap says they do. Do not reinterpret a passing unit test as proof that the packaged Windows workflow is usable, responsive, understandable, or efficient.

Findings from real lawful song/score sessions should become GitHub issues and, where they reveal reusable defect patterns, engineering-memory entries.

## Documentation discipline

Update documentation in the same PR when behavior changes. Specifically:

- update `PROJECT_PLAN.md` when milestone truth or roadmap direction changes;
- update `docs/project-status.yaml` whenever current state/continuation changes;
- add/update ADRs for implementation-level architectural choices;
- update README/user docs when real user-facing capability changes;
- update the error ledger for significant/recurring root-cause lessons.

Do not create parallel duplicate roadmaps or architecture sources of truth.

## Git content / copyright judgment

This project processes material that may be lawful for personal authoring but not lawful to redistribute in a public repository. Therefore use a conservative commit boundary.

Never commit by default:

- commercial recordings or derived copyrighted stems;
- copyrighted Guitar Pro/MusicXML/tab source files acquired for personal use unless redistribution rights are explicit;
- commercial/private PSARC or CDLC packages;
- CFSM exports containing private library data;
- Steam profiles/save data;
- extracted Ubisoft-derived content;
- private generated song-project workspaces.

Allowed committed fixtures should be synthetic, original, public-domain, or clearly licensed for redistribution. Metadata-only evidence that does not embed restricted content may be committed when useful and safe.

If rights are unclear, keep the asset out of Git and continue with a local/private fixture or ask for human guidance if the asset is required.

## ADR autonomy

Agents may create ADRs for routine implementation choices that remain inside current product direction. ADRs must state context, decision, alternatives, reasons, and consequences. Major architecture shifts not already authorized by the roadmap require human direction before implementation.

## Human decision boundary

Escalate only for:

- fundamental product-direction change;
- major unauthorized architecture change;
- new paid service or meaningful recurring cost;
- license change;
- destructive/irreversible migration;
- security/privacy authority change;
- secret/credential problem requiring the owner;
- publication, release, distribution, or copyright decision requiring authorization;
- genuinely ambiguous requirements with materially different outcomes.

Routine coding, test, refactoring, documentation, and implementation decisions should be made autonomously when repository evidence supports them.

## End-of-run continuity record

Before ending a run that changed repository reality, ensure `docs/project-status.yaml` records:

- current roadmap milestone;
- verified active PRs/blockers at the time of the update;
- what was just completed or opened;
- the exact next continuation point;
- any human decision required.

Do not put speculative future work in the status file when the roadmap already owns that information.
