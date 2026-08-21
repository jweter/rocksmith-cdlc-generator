# Desktop Theme v1

This is the first visible adoption pass for issue #305's design-system foundation.
It changes presentation only; it does not change workflow authority, review gates,
validation meaning, provenance, source rights, arrangement data, or packaging rules.

## Visual direction

The packaged Windows app now follows #305's **dark-first authoring** direction with a
restrained studio/workbench visual language intended for long editing sessions:

- charcoal application canvas instead of raw platform-default gray
- layered dark work surfaces with consistent borders
- high-contrast Segoe UI typography through the existing shared type scale
- a violet accent reserved for focus, progress, selection, and primary actions
- consistent button padding and interaction states
- stronger Notebook tab hierarchy
- cleaner dark Treeview rows, headings, and selected rows
- consistent Entry/Combobox/Spinbox focus treatment
- classic Tk Text/Canvas widgets are normalized into the same visual system
- semantic PASS/WARNING/FAIL/STALE/REVIEW REQUIRED/INFO foregrounds are adjusted for
  readable contrast on dark surfaces while preserving their existing symbol + text
- primary workflow actions are visually distinct without changing what they do
- the exact guided next action gains a non-color-only `NEXT REQUIRED ACTION →` cue
- the existing variable-tempo audition control is surfaced as
  `Click Track · Audition Beat Grid` without changing its timing behavior

The theme lives in `desktop_theme.py`; legacy widget-tree adoption lives in
`desktop_polish.py`. Screens should consume named styles rather than adding new one-off
color/font literals.

## Why `clam`

The packaged app selects ttk's bundled `clam` theme when available. Native Windows ttk
themes can ignore requested background/border colors, which makes a deliberate dark
visual system unreliable. `clam` provides predictable styling while remaining entirely
inside Tk/ttk: no web runtime, no third-party theme dependency, and no additional
packaged assets.

If `clam` is unavailable, the application leaves the platform theme active and applies
the same named style registry as far as that theme permits.

## Accessibility and state

Color is never the sole carrier of workflow state. Existing state text remains intact,
and semantic status styles retain their symbol + label convention. Selection uses both
background contrast and existing text/row context. Disabled primary actions receive a
distinct muted treatment. Stale/review-required/fail semantics are not softened or
hidden by the theme.

## Product Reality acceptance check

After downloading a Windows artifact that contains this change:

1. Confirm the title bar shows the expected version/build SHA.
2. Open the representative `For Whom the Bell Tolls` project.
3. Confirm the main shell is visibly dark-themed: charcoal canvas, layered work
   surfaces, violet progress/primary actions, and cleaner hierarchy.
4. Confirm the guided action area places `NEXT REQUIRED ACTION →` directly beside the
   real dynamic action button when an action is available.
5. Open Song Workspace and confirm tabs, tables, form controls, text areas, canvases,
   and progress bars use the same dark visual language.
6. On Timeline, confirm the existing timing audition toggle reads
   `Click Track · Audition Beat Grid` and behaves exactly like the previous
   variable-tempo click control.
7. Confirm PASS/WARNING/FAIL/stale/review-required text remains easy to distinguish and
   readable against the dark background.
8. Confirm controls retain their prior enabled/disabled behavior and workflow routing.
9. Confirm validation/review/source-rights language remains unchanged and legible.
10. Confirm large tables and the Review Queue remain readable at 100% Windows scaling.
11. Capture one main-shell screenshot and one Song Workspace screenshot with the build
    identity visible so later polish can be compared against a known artifact.

## Deliberate limits of v1

This pass does not redesign information architecture, replace Tkinter, introduce icon
assets, or rewrite individual workflow panels. It establishes a coherent dark visual
shell first. Later #305 slices can safely introduce reusable cards/status badges,
dense review-queue presentation, role-specific workflow summaries, and panel-specific
improvements on top of the shared theme.
