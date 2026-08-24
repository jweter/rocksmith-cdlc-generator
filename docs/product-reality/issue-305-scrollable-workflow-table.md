# Scrollable primary workflow table (#305)

## Product symptom

The main Workflow tab can contain more steps than fit vertically, while its
Step / reason column can contain diagnostic or recovery text wider than a
constrained laptop window. The table had neither vertical nor horizontal
scrolling, so rows and explanations could become unreachable or clipped.

## Resolution

The Workflow `Treeview` now sits in an expanding frame with:

- a visible vertical scrollbar for the full workflow sequence;
- a visible horizontal scrollbar for long step/reason explanations;
- two-way `yview` / `xview` command bindings;
- grid weights that keep the table expanding with the window.

The workflow plan, statuses, modes, ordering, and reasons are unchanged.

## Regression protection

`tests/test_desktop_score_tab_layout.py` builds the real layout using
no-display widget stand-ins and verifies both scrollbar orientations,
commands, callbacks, and placements.
