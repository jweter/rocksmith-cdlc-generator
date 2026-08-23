# Product Reality defect: redundant/blank "Next action" callout under the guided Song progress panel

## Observed symptom

Static code-inventory review (this repository has no rendering-based UI test
precedent to reproduce against a live packaged build; see
`docs/ui/desktop-ui-audit.md` for why) of the shipped `cdlc-desktop` shell
(`diagnostic_guided_desktop.LiveDiagnosticsGuidedDesktopApp` →
`guided_desktop.GuidedDesktopApp` → `desktop_shell.ProductDesktopApp` →
`desktop_app.DesktopApp`) found that `DesktopApp._build_layout` builds a
"Next action" `ttk.LabelFrame` callout bound to `next_action_var`, which
starts as an empty string and is only ever populated by
`DesktopApp.refresh_project`.

`GuidedDesktopApp._build_layout` stacks its own "Song progress" panel
(headline + detail + a `Next Step`/"Continue Automatically" action button)
directly above that same callout, via `before=children[1]`. Both panels are
driven by the exact same source of truth:
`build_multi_arrangement_workflow_plan(project)` (`GuidedDesktopApp.refresh_project`
calls `build_song_readiness(build_multi_arrangement_workflow_plan(project))`
for its own headline/detail text, after first calling
`super().refresh_project()` -- `DesktopApp.refresh_project` -- which sets
`next_action_var` from the identical plan's next step).

Result on the real shipped shell:

- **Before any project is open:** the "Song progress" panel correctly shows
  "Open or create a song project to begin", but the "Next action" callout
  directly beneath it renders as a blank, framed empty box (`next_action_var`
  is never set at this point) -- a first-time user sees an unexplained empty
  panel immediately under the real guidance.
- **After a project is open:** the callout duplicates the same next-step
  information already shown, more legibly, in the "Song progress" detail
  line, just in its raw `"{step.title}: {step.reason}"` form straight from
  the workflow plan -- exactly the "developer-facing/raw-state presentation"
  PROJECT_PLAN.md's #305 asks the guided shell to reduce, and the opposite of
  "prefer progressive disclosure: simple normal path, detailed diagnostics on
  demand."

## Root cause

`next_action_var`/the callout `LabelFrame` were local implementation details
of `DesktopApp._build_layout` with no addressable reference, so a subclass
that wanted to present the same underlying information more usefully (as
`GuidedDesktopApp` does) had no way to suppress the original raw copy --
both were simply left visible, one stacked on the other.

## Fix

- `desktop_app.py`: the callout is now kept as `self.next_action_callout`
  instead of a `_build_layout`-local variable, so subclasses can address it.
- `guided_desktop.py`: `GuidedDesktopApp._build_layout` calls
  `self.next_action_callout.pack_forget()` immediately after the base layout
  builds it, removing the blank/duplicate box from the guided shell. The
  underlying raw per-step detail remains fully available as the existing
  Workflow tab's step table (`workflow_tree`), which continues to serve as
  the expandable diagnostics surface #305 asks to retain.
- The non-guided `DesktopApp`/`ProductDesktopApp` layout (not part of the
  shipped `cdlc-desktop` entry point, but still a real usable shell) is
  unchanged and keeps showing its own "Next action" callout, since it has no
  separate guided panel duplicating that information.

No mapping, validation, provenance, packaging, or human-review-gate logic
changed; this is a presentation-only fix.

## Regression coverage

`tests/test_guided_desktop_next_action_layout.py` exercises the real
`_build_layout` chain (`GuidedDesktopApp` → `ProductDesktopApp` →
`DesktopApp`) against recording stand-ins for the `tkinter`/`ttk` classes it
constructs, following the no-display-server convention in
`tests/test_desktop_score_tab_layout.py`:

- `test_guided_shell_hides_the_redundant_base_next_action_callout` asserts
  the guided shell calls `pack_forget()` on the base callout.
- `test_guided_shell_still_builds_a_populated_song_progress_panel` asserts
  the guided shell's own panel and action button are still built and remain
  the single visible next-step surface.
- `test_base_desktop_app_still_shows_its_own_next_action_callout` asserts
  the non-guided shell's layout is unaffected.

Full suite: `python -m pytest -q` → 1375 passed, 0 failed (1372 baseline +
3 new), Python 3.12 with `dev,beat` extras (`python3-tk` installed locally
for sandbox verification only, matching this repo's established
precedent). Also ran `python -m compileall`, `python -m pip check`,
`cdlc --help`, and `scripts/check_automation_readiness.py` -- all clean.
