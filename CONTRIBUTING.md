# Contributing to Rocksmith CDLC Generator

Thanks for helping improve the project. Contributions should preserve the project's core goal: produce high-quality, reviewable Rocksmith 2014 arrangement drafts while keeping musical authority, provenance, validation, and packaging safety explicit.

## Before you start

- Read `README.md`, `PROJECT_PLAN.md`, `AGENTS.md`, `docs/project-status.yaml`, and the relevant architecture/authoring documentation.
- Search existing issues and pull requests before opening new work.
- Prefer focused changes with a clear user-visible or engineering benefit.
- Do not add copyrighted commercial audio, commercial tablature/score files, PSARC packages, player profiles, credentials, secrets, or other private data to the repository.

## Product invariants

Contributions must not weaken these boundaries:

1. Bass, Lead Guitar, and Rhythm Guitar are equal first-class product targets.
2. Imported notation, audio-derived evidence, and user-approved edits keep explicit provenance.
3. Low-confidence or ambiguous musical decisions remain reviewable rather than silently promoted to truth.
4. Human-confirmation gates remain authoritative where the project requires them.
5. Validation failures block downstream packaging where defined by the current workflow.
6. Generated work is staged project-locally before anything is installed into Rocksmith.
7. The application must not modify the live Rocksmith installation, official DLC, player profile, or unrelated user files as a side effect of analysis.
8. Third-party tools remain behind explicit adapters and documented responsibility boundaries.

## Development workflow

Use a branch and pull request for changes intended for `main`.

A good pull request should:

- explain the problem and intended behavior;
- keep scope bounded;
- include tests for new behavior and regressions;
- update documentation when product reality, architecture, or workflow behavior changes;
- preserve backward compatibility unless the change intentionally and explicitly replaces an old contract;
- identify any new dependency, external executable, model, network access, or security boundary.

## Quality preflight

After installing the development extras, run the repository-standard gate before opening or updating a PR:

```bash
python -m pip install -e ".[dev,beat]"
python scripts/quality_preflight.py
```

On Windows, changes touching PSARC packaging or the desktop bridge should also run:

```powershell
python scripts/quality_preflight.py --windows-bridge
```

The preflight mirrors the portable CI contract: autonomous-development readiness, Python bytecode compilation, pytest, the installed `cdlc` entry point, dependency consistency, and diff hygiene. The optional Windows mode also builds the pinned Rocksmith2014.NET PSARC bridge. CI remains authoritative.

## Testing

Run the relevant automated tests locally when practical. CI is authoritative for merge readiness.

Do not merge a change while required checks are failing, pending due to a known problem, or reporting unresolved review findings.

For user-facing Windows changes, test the packaged application path where practical rather than relying only on module-level behavior. Product Reality findings should be recorded as evidence-backed issues rather than being dismissed as cosmetic if they block or confuse the normal path.

## Defect fixes

Fix the shared root cause when possible rather than adding local exceptions. A defect fix should normally include a regression test that would have failed before the fix.

If the same failure class has appeared before, cross-reference the recurring-defect tracking issue and document the prevention pattern.

## Dependencies

Keep dependencies deliberate and minimal. New dependencies should have a clear project benefit, compatible licensing, reasonable maintenance health, and an acceptable local-first/privacy footprint.

Do not bundle third-party binaries, models, or copied source merely for convenience when a documented bootstrap or adapter boundary is more appropriate.

## Documentation

Documentation is part of the product. Update roadmap, project-status, operator guidance, ADRs, or feature documentation whenever a change would otherwise make those materials stale or misleading.

## Pull request review

A pull request is ready to merge only when:

- required CI is green;
- the change is mergeable without unresolved conflicts;
- relevant review comments are resolved;
- tests cover the important behavior;
- documentation is current;
- no provenance, safety, source-rights, validation, or human-review gate has been weakened merely to make the change pass.

## Licensing and contributions

This repository is publicly viewable but is not released under a permissive open-source license. See `LICENSE` before reusing project code.

By submitting a contribution, you agree to the contribution terms stated in `LICENSE`.
