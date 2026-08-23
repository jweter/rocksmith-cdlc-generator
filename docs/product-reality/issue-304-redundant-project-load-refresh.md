# Product Reality defect: opening a project refreshed the whole shell twice

## Observed symptom

`LiveDiagnosticsGuidedDesktopApp.load_project` -- the real `cdlc-desktop`
entry point's project-open handler -- called `self.refresh_project()` twice
for every successful project open: once inside the load's try/finally block,
and again immediately afterward, purely to produce one
`"Workflow state: ..."` diagnostic log line once
`_diagnostic_project_load_in_progress` had been reset to `False`.

Each `refresh_project()` call is not cheap: through the
`DesktopApp` -> `ProductDesktopApp` -> `GuidedDesktopApp` ->
`LiveDiagnosticsGuidedDesktopApp` chain it recomputes the multi-arrangement
workflow plan (twice per call -- once directly in `DesktopApp.refresh_project`
and again inside `GuidedDesktopApp.refresh_project`'s `build_song_readiness`
call), rebuilds the workflow/score/rights tables, and refreshes every other
open shell window (Song Workspace, Metadata & Cover, Tones & Regions, XML
Export, DLC Builder preparation, Product Reality Recorder). Calling
`load_project` therefore recomputed the workflow plan four times and
re-rendered every open window's state twice on a single project open, for no
observable benefit beyond one log line -- pure workflow friction (#305
"Reduce developer-facing/raw-state presentation" and #304 priority-6 lower-
severity friction), and a case of the #193 "do the expensive thing more than
once for no reason" pattern (distinct from #193's usual stale-derivative
flavor, but the same discipline of tracking recurring engineering waste).

Every other shell's `load_project` (the base `DesktopApp.load_project`) calls
`refresh_project()` exactly once; this subclass was the only one that doubled
it.

## Root cause

`_diagnostic_project_load_in_progress` was introduced to suppress the
workflow-state diagnostic log line during the shell's own internal refresh
(so it would not fire before `_render_persisted_diagnostics()` had reset
`_last_workflow_diagnostic`), but the mechanism used to get the log line to
fire "for real" afterward was to re-run the *entire* refresh a second time
with the guard cleared, rather than extracting just the small
compute-and-log-if-changed step into its own helper.

## Fix

- `diagnostic_guided_desktop.py`: extracted the workflow-state log check into
  `_log_workflow_state_if_changed()`. `refresh_project()` now calls that
  helper instead of inlining the check. `load_project()` now calls the full
  `refresh_project()` cascade exactly once (inside the try/finally, matching
  every other shell), then calls only the cheap helper afterward to produce
  the same `"Workflow state: ..."` log line at the same point in the
  sequence -- observable log output is unchanged, but the expensive refresh
  cascade (and the workflow-plan recomputation within it) now runs once per
  project open instead of twice.

This is a pure internal refactor: no widget, workflow-plan, mapping,
provenance, validation, or packaging behavior changed, and the two
diagnostic log lines a user sees ("Opened project: ...", "Project opened:
...", "Workflow state: ...") are identical in content and order to before.

## Regression protection

`tests/test_desktop_diagnostics.py::test_successful_project_load_refreshes_workspace_state_exactly_once`
stubs `refresh_project` on a fake shell object and asserts it is invoked
exactly once by `load_project`, and that the three diagnostic log lines still
appear in the same order. Verified to fail against the pre-fix code (asserts
`len(refresh_calls) == 1`, which failed with `2` before this fix).

Full suite: `python -m pytest -q` -> 1377 passed, 0 failed (1376 baseline + 1
new). Also ran `python -m compileall`, `python -m pip check`, `cdlc --help`,
`scripts/check_automation_readiness.py`, and `scripts/quality_preflight.py`
(via `scripts/quality_preflight.py` itself) -- all clean.

## Safety / authority boundary

No mapping, validation, provenance, timing, packaging, or human-review-gate
logic changed. This only removes a redundant second refresh cascade that
produced no new information.

## Residual risk

None identified. The duplicate-refresh pattern was specific to
`LiveDiagnosticsGuidedDesktopApp.load_project`; the base `DesktopApp` and
`ProductDesktopApp`/`GuidedDesktopApp` load paths already called
`refresh_project()` exactly once.
