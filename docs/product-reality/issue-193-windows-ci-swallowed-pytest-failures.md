# Product Reality defect: Windows CI silently ignored pytest failures; 6 tests were red on Windows for an unknown period

## Observed symptom

Asked to check whether "everything works the way it should," a full local
`python -m pytest -q` run on Windows showed 6 failing tests that this
session had previously (across five earlier PRs) treated as "pre-existing,
unrelated, confirmed via `git stash`" -- true as far as it went, but nobody
had actually root-caused *why* main carried 6 permanently-red tests, or
noticed that CI was reporting success anyway.

## Root cause 1: `ci.yml`'s Windows job could never fail on a pytest failure

`.github/workflows/ci.yml`'s `windows-compat` job ran:

```yaml
- name: Compile and run Python tests
  shell: pwsh
  run: |
    python -m compileall -q src tests
    python -m pytest -q
    cdlc --help
```

Under PowerShell, a nonzero exit code from an external command does not
stop script execution or fail the step unless it is the *last* statement
(or `$LASTEXITCODE` is explicitly checked). Because `cdlc --help` ran
*after* `python -m pytest -q` and always succeeds, its exit code silently
overwrote pytest's failure. Confirmed directly against the real GitHub
Actions run (`gh run view --log`): the actual Windows job log shows
`6 failed, 1636 passed, ... in 47.15s` from pytest itself, immediately
followed by the step, job, and workflow all reporting `"conclusion":
"success"`.

The sibling `ubuntu-latest` `test` job in the same file already ran
`compileall`, `pytest`, and `cdlc --help` as three *separate* steps, so it
correctly failed on any pytest failure -- which is exactly why these same 6
tests never showed up as a red Linux CI check, only a real-but-invisible
Windows one. `docs/project-status.yaml`'s own `automation_contract` requires
both `CI` and `Windows Desktop` to pass before merge, but `CI`'s Windows job
was never actually capable of blocking a merge on a Windows-only pytest
regression.

## Root cause 2: inconsistent relative-path serialization across ~15 call sites

Separately, of the ~50 call sites in `src/rocksmith_cdlc_generator/` that
build a project-relative path with `X.relative_to(project)` for storage in
a JSON manifest/report field, the overwhelming majority already correctly
call `.as_posix()` for a portable, OS-independent string. A minority instead
called plain `str(...)`, which renders with the *host OS's* separator --
backslashes on Windows. On Linux CI this is invisible (POSIX separators
either way); on Windows it produced fields like `"charts\bass_mapped.json"`
instead of the `"charts/bass_mapped.json"` every test (correctly) expected,
since JSON manifests are meant to be portable regardless of which OS built
the project.

Affected production call sites (all fixed to `.as_posix()`):

- `authoring_export.py` (6 sites: `source_mapping`, `source_tempo_map` x2,
  `output_xml` x2, `source_chart`)
- `metadata_integration.py` (`recording_context_path`)
- `metadata_providers.py` (`source_report`)
- `project.py` (`source_project_path`, normalized-audio `ArtifactRecord.path`)
- `project_score.py` (`output_relative_path`, `relative_stored`)
- `project_source_inventory.py` (`receipt_path`, `rights_review_path`)
- `source_workflow.py` (`relative_output` in the intake receipt)
- `workflow_plan.py` (`_ImportedBassSource.relative_path` -- inconsistent
  with a sibling field two lines away in the same function that already
  used `.as_posix()`)

Two tests (`test_project_score.py`,
`test_source_rights_review.py::test_inventory_uses_review_without_mutating_original_receipt`)
happened to pass before this fix only because *both* sides of their
comparison independently called plain `str(...relative_to(...))`, so the
wrong (backslash) format matched itself; they were updated to compare
against `.as_posix()` to match the now-corrected production format, rather
than weakened to keep tolerating backslashes.

## Root cause 3 (unrelated, same symptom bucket): one CLI-parsing test asserted POSIX-only path formatting

`tests/test_source_rights_cli.py::test_parser_accepts_explicit_local_rights_review`
asserted `str(args.project) == "projects/song"` where `args.project` is
`argparse`'s own `Path("projects/song")` from a raw CLI argument string --
unrelated to any project JSON manifest. This is not a product bug at all,
just a test written against Unix path-separator assumptions. Fixed by
comparing `args.project == Path("projects/song")` (OS-agnostic `Path`
equality) instead of a hardcoded forward-slash string.

## Fix

- `ci.yml`: split the Windows job's combined step into three separate
  steps (`Compile source`, `Run tests`, `Verify CLI entry point`), matching
  the already-correct Linux job's pattern, so a Windows-only pytest failure
  now actually fails the required `CI` check.
- 9 production files: standardized every outlier `str(X.relative_to(project))`
  call site to `X.relative_to(project).as_posix()`.
- 3 test files: updated two test-side comparisons that were coincidentally
  matching the old backslash format, and rewrote the CLI-parsing test to use
  `Path` equality instead of a hardcoded separator.

No mapping, validation, provenance, timing, or packaging *logic* changed --
every fix here is either CI-workflow plumbing or path-string formatting.

## Regression coverage

Full suite: `python -m pytest -q` -> **1642 passed, 0 failed, 3 skipped**
(previously 1636 passed, 6 failed on Windows -- every existing test that
exercised one of the 9 fixed call sites already carried the correct
forward-slash expectation, so no new tests were needed beyond the two
test-side comparison fixes above). `python -m compileall -q src tests`,
`cdlc --help`, and `python scripts/check_automation_readiness.py` all
clean.

The `ci.yml` fix itself has no direct test (it's CI configuration); it will
be self-verifying on this PR's own required Windows `CI` check, which
should now show its own real pytest result rather than a masked one.
