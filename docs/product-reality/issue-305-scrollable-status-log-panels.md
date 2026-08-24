# Scrollable desktop status and log panels (#305)

## Product symptom

The base desktop shell's Rights / Provenance status and Activity Log were
plain expanding `tk.Text` widgets without visible scrollbars. The Activity
Log is intentionally unbounded during a session, and rights/provenance
diagnostics can grow beyond the available panel height. Content remained
technically reachable through mouse-wheel or keyboard behavior, but the UI
provided no visible affordance or position indicator and was poor on
constrained laptop layouts.

## Resolution

Both panels now use the same explicit composition:

- a dedicated expanding frame;
- the existing read-only text widget;
- a permanently visible vertical `ttk.Scrollbar`;
- two-way `yview` / `yscrollcommand` binding.

No log, rights classification, source identity, or review authority changes.

## Regression protection

`tests/test_desktop_score_tab_layout.py` builds the real layout against the
repository's no-display widget stand-ins and verifies the scrollbar
orientation, command binding, callback binding, and visible right-side
placement for both panels.
