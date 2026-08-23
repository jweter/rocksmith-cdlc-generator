# Product Reality defect: a human-confirmed Lead/Rhythm mapping did not count as "configured"

## Observed symptom

`SongWorkspaceSnapshot`/`ValidationDashboardRow` compute each arrangement's
`configured` flag purely from `manifest.arrangement_instruments` -- a field that is
fixed once at project creation (`create_project(..., instruments=...)`). The shipped
desktop shell always creates new projects with `instruments=["bass", "lead",
"rhythm"]`, so this defect was invisible from that one surface. But the documented
CLI "deterministic engine" path (`cdlc new --instrument bass`, or `cdlc new` with no
`--instrument` at all, which defaults to Bass-only) can create a project that never
declares Lead or Rhythm. `cdlc-score-map confirm lead <track>` -- the normal way to
human-confirm a Lead/Rhythm mapping -- has no `arrangement_instruments` check and
happily records a confirmed mapping regardless. `multi_arrangement_plan`'s
`_confirmed_guitar_roles` then builds real Lead/Rhythm workflow steps, generates real
`lead_validation_report.json`/`rhythm_validation_report.json` files, and drives real
draft/export state for that role from the confirmed mapping alone -- it never consults
`arrangement_instruments` either.

The result: a role a user actively mapped, human-confirmed, and validated could still
report `configured=False` in the Song Workspace snapshot. `validation_dashboard.py`
already deliberately excludes unconfigured rows from its aggregate counts (`configured
= [row for row in rows if row.configured]`), so a genuinely FAIL or unreadable Lead
validation report was silently dropped from `blocked_count`/`validation_needed_count`,
and the dashboard's own `NOT_CONFIGURED` row told the user to "Enable this arrangement
in the project before validation is required" -- even though they had already done the
one thing (`cdlc-score-map confirm`) the project actually requires. The same
`configured_roles` set also gated `song_workspace.py`'s own `any_validation_problem`
check and the `configured_arrangements` list used for export readiness, so an INVALID
(unreadable) Lead validation report for an undeclared-but-confirmed role did not block
overall project health the way the identical situation does for a manifest-declared
role (see `test_unreadable_validation_report_blocks_old_xml_readiness`).

## Root cause

Two independent signals both claim to answer "which arrangement roles are really part
of this project": the manifest's `arrangement_instruments` (set once, at creation,
only by the desktop shell or `cdlc new --instrument`), and human-confirmed score
mapping (set later, any time, by `cdlc-score-map confirm` or the desktop Score &
Mappings tab, and the only signal the actual workflow planner consults to build real
Lead/Rhythm work). `song_workspace.py` trusted only the first signal when computing
`configured`, so the two could diverge for any project not created through the one
GUI path that happens to declare all three up front -- exactly the class of
stale/inconsistent-derived-state bug #193 tracks.

## Fix

`song_workspace.py`'s `configured_roles` now also includes any role with a
human-confirmed score mapping (`score.mapping_for(role).human_confirmed`), matching
the same signal `multi_arrangement_plan._confirmed_guitar_roles` already uses to
decide whether a role's Lead/Rhythm workflow/validation is real. This does not weaken
any gate: a role only becomes "configured" once it has been explicitly human-confirmed
(or was declared at creation), so nothing is silently promoted to configured without
an explicit human action already on record.

## Regression protection

- `tests/test_song_workspace.py::test_human_confirmed_mapping_marks_undeclared_role_configured`
  registers a bass-only project (`arrangement_instruments=["bass"]`) with a
  human-confirmed Lead mapping and asserts the Lead arrangement reports
  `configured=True` (Rhythm, never confirmed, stays `False`). Verified to fail
  pre-fix (`configured=False`).
- `tests/test_song_workspace.py::test_human_confirmed_role_invalid_report_still_blocks_health`
  gives that same undeclared-but-confirmed Lead role an unreadable validation report
  and asserts overall `health == "BLOCKED"`. Verified to fail pre-fix
  (`health == "IN_PROGRESS"`, i.e. the broken Lead report was silently ignored).

Full suite: `python -m pytest -q` -> 1378 passed, 0 failed (1376 baseline + 2 new).
Also ran `python -m compileall`, `python -m pip check`, `cdlc --help`,
`scripts/check_automation_readiness.py`, and `scripts/quality_preflight.py` -- all
clean.

## Safety / authority boundary

No mapping, validation, provenance, timing, or packaging authority changed. A role
only becomes `configured` when it was declared at creation or explicitly
human-confirmed via mapping -- the same authority-bearing signal the workflow planner
already relies on. No human-review gate is weakened; if anything, this closes a path
by which a real FAIL/INVALID validation problem for an actively-worked role could be
silently excluded from the dashboard's blocking count.
