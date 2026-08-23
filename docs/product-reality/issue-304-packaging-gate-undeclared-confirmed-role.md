# Product Reality defect: a human-confirmed Lead/Rhythm role was invisible to the packaging gate

## Observed symptom

`arrangement_gate.configured_arrangement_roles(project_dir)` -- the function that
decides both which arrangements `require_configured_arrangements_ready` must
validate before packaging and which arrangements `prepare_dlcbuilder_project`
actually builds into the DLC Builder project -- read only
`manifest.arrangement_instruments`, a field fixed once at project creation
(`create_project(..., instruments=...)`). The shipped desktop shell always
creates new projects with all three roles declared, so this defect was
invisible from that one surface. But the documented CLI "deterministic
engine" path (`cdlc new --instrument bass`, or `cdlc new` with no
`--instrument` at all, which defaults to Bass-only) can create a project that
never declares Lead or Rhythm. `cdlc-score-map confirm lead <track>` -- the
normal way to human-confirm a Lead/Rhythm mapping -- has no
`arrangement_instruments` check and happily records a confirmed mapping
regardless; `cdlc build-guitar-chart`, `cdlc export --instrument lead`, and
`cdlc validate --instrument lead` are likewise ungated by it, so a user on
this path can fully author, validate, and export a real Lead arrangement.

Because `configured_arrangement_roles` never consulted the human-confirmed
mapping, that real Lead arrangement was invisible to two authority-bearing
call sites:

- `require_configured_arrangements_ready` (called from
  `prepare_dlcbuilder_project` and `build_staging.py`'s staging/launch paths)
  never ran Lead validation as part of the pre-package gate, so a genuinely
  FAIL Lead arrangement could **not** block packaging the way an identical
  FAIL for a manifest-declared role already does.
- `prepare_dlcbuilder_project`'s build loop
  (`for role in configured_arrangement_roles(project_dir): ...`) never
  iterated Lead, so a fully mapped, validated, exported, PASSing Lead
  arrangement was silently **excluded from the shipped DLC Builder project**
  even though the user did every step the workflow asks for.

`psarc_inspection.py` reads the same function to decide which arrangements a
built PSARC is expected to contain, so registration/verification would also
have silently expected Bass-only for a project that in reality carried a
real, human-confirmed Lead arrangement.

## Root cause

The same two independent signals from
`docs/product-reality/issue-304-undeclared-confirmed-role-not-configured.md`
(PR #393) recur here, one layer deeper: the manifest's
`arrangement_instruments` (set once, at creation) and human-confirmed score
mapping (set later, any time, and the only signal
`multi_arrangement_plan._confirmed_guitar_roles` already treats as real
Lead/Rhythm project work). PR #393 fixed the Song Workspace dashboard's
`configured` flag to consult both signals, but `arrangement_gate.py` -- the
actual packaging-gate and DLC-build-selection code, reachable independently
of the desktop Song Workspace via the plain CLI -- still trusted only the
first signal. Exactly the class of stale/inconsistent-derived-state bug #193
tracks, and exactly the kind of second instance the #304/#193 audit thread
expects to keep finding.

## Fix

`arrangement_gate.configured_arrangement_roles` now also includes any role
with a human-confirmed score mapping (`score.mapping_for(role).human_confirmed`),
appended after the manifest-declared roles in canonical Bass/Lead/Rhythm
order, matching the same signal `multi_arrangement_plan._confirmed_guitar_roles`
and the already-fixed `song_workspace.configured_roles` both use. Loading the
score contract reuses `score_mapping_review.load_score_for_mapping_review`,
which fails closed (returns no additional roles) on any missing/invalid/
tampered score contract, mirroring `song_workspace._score_or_none`. This does
not weaken any gate: a role only becomes "configured" once it has been
explicitly human-confirmed (or was declared at creation), so nothing is
silently promoted into the packaging path without an explicit human action
already on record.

## Regression protection

- `tests/test_arrangement_gate.py::test_configured_arrangement_roles_includes_undeclared_human_confirmed_role`
  registers a bass-only project (`arrangement_instruments=["bass"]`) with a
  human-confirmed Lead mapping and asserts `configured_arrangement_roles`
  returns `["bass", "lead"]`. Verified to fail pre-fix (`["bass"]`).
- `tests/test_arrangement_gate.py::test_gate_blocks_on_undeclared_human_confirmed_role_failure`
  gives that same undeclared-but-confirmed Lead role a FAIL validation result
  and asserts `require_configured_arrangements_ready` raises
  `PackagingBlockedError` naming `lead`. Verified to fail pre-fix (did not
  raise).
- `tests/test_arrangement_gate.py::test_configured_arrangement_roles_ignores_unconfirmed_mapping`
  asserts a proposed-but-not-yet-human-confirmed mapping does **not** expand
  the configured role set, guarding against over-correcting into silently
  trusting unconfirmed evidence.

Full suite: `python -m pytest -q` -> 1382 passed, 0 failed (1379 baseline +
3 new). Also ran `python -m compileall`,
`python -m pip check`, `cdlc --help`, `scripts/check_automation_readiness.py`,
and `scripts/quality_preflight.py` -- all clean.

## Safety / authority boundary

No mapping, validation, provenance, timing, or packaging authority changed.
A role only becomes part of the packaging gate/build set when it was
declared at creation or explicitly human-confirmed via mapping -- the same
authority-bearing signal the workflow planner already relies on. No
human-review gate is weakened; if anything, this closes a path by which a
real FAIL Lead/Rhythm arrangement could bypass the pre-package validation
gate entirely, and by which a real PASSing Lead/Rhythm arrangement the user
completed could be silently dropped from the shipped DLC.

## Residual risk

`psarc_inspection.py` consumes the same corrected `configured_arrangement_roles`,
so its expectations should now match reality for this scenario too, but this
change did not add a dedicated `psarc_inspection.py` regression test -- its
existing test coverage exercises it against the same function, so any future
divergence there would need its own audit pass.
