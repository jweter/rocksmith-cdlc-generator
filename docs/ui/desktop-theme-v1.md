# Desktop Theme v1

This is the first visible adoption pass for issue #305's design-system foundation.
It changes presentation only; it does not change workflow authority, review gates,
validation meaning, provenance, source rights, arrangement data, or packaging rules.

## Visual direction

The packaged Windows app now uses a restrained studio/workbench visual language:

- soft neutral application canvas instead of raw platform-default gray
- clean work surfaces and consistent borders
- Segoe UI typography through the existing shared type scale
- a blue-violet accent reserved for focus, progress, selection, and primary actions
- consistent button padding and interaction states
- stronger Notebook tab hierarchy
- cleaner Treeview rows, headings, and selected rows
- consistent Entry/Combobox/Spinbox focus treatment
- shared semantic PASS/WARNING/FAIL/STALE/REVIEW REQUIRED/INFO styles remain available
- primary workflow actions are visually distinct without changing what they do

The theme lives in `desktop_theme.py`. Screens should consume named styles rather than
adding new one-off color/font literals.

## Why `clam`

The packaged app selects ttk's bundled `clam` theme when available. Native Windows ttk
themes can ignore requested background/border colors, which makes a deliberate visual
system unreliable. `clam` provides predictable styling while remaining entirely inside
Tk/ttk: no web runtime, no third-party theme dependency, and no additional packaged
assets.

If `clam` is unavailable, the application leaves the platform theme active and applies
the same named style registry as far as that theme permits.

## Accessibility and state

Color is never the sole carrier of workflow state. Existing state text remains intact,
and semantic status styles retain their symbol + label convention. Selection uses both
background contrast and existing text/row context. Disabled primary actions receive a
distinct muted treatment.

## Product Reality acceptance check

After downloading a Windows artifact that contains this change:

1. Confirm the title bar shows the expected version/build SHA.
2. Open the representative `For Whom the Bell Tolls` project.
3. Confirm the main shell is visibly themed: neutral canvas, cleaner controls, violet
   progress/primary actions, and more consistent spacing/typography.
4. Open Song Workspace and confirm tabs, tables, form controls, and progress bars use
   the same visual language.
5. Confirm no button disappeared, changed label, or changed enabled/disabled behavior.
6. Confirm validation/review/source-rights language remains unchanged and legible.
7. Confirm large tables and the Review Queue remain readable at 100% Windows scaling.
8. Capture one main-shell screenshot and one Song Workspace screenshot with the build
   identity visible so later polish can be compared against a known artifact.

## Deliberate limits of v1

This pass does not redesign information architecture, replace Tkinter, introduce icon
assets, or rewrite individual workflow panels. It establishes a coherent visual shell
first. Later #305 slices can safely introduce reusable cards/status badges, denser
review-queue presentation, and panel-specific improvements on top of the shared theme.
