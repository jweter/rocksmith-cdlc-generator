# Product Reality defect: Score & Mappings gate controls unreachable on a real viewport

## Observed symptom

Reproduced on packaged Windows build `v0.1.0 · 80b591fd` during a fresh For Whom the
Bell Tolls project. After rights review and score registration, the workflow
correctly stopped at the human `score-arrangements` gate and highlighted
`Review Score Tracks`, but the Score & Mappings tab only showed the track
table. The actual Bass/Lead/Rhythm mapping comboboxes and Confirm buttons were
laid out *below* that table and were clipped by the reduced notebook height
created by the readiness/next-action/live-diagnostics chrome stacked above the
notebook. The tab had no vertical scroll path, so on the tested 1600x960
Windows laptop the required controls were unreachable and the project could
not advance. This was a normal-path blocker, not user error.

## Root cause

`DesktopApp._build_layout()` packed the "Score & Mappings" tab strictly
top-to-bottom with `pack(fill="x")`/`pack(fill="both", expand=True)`: track
header, then a fixed `height=8` `Treeview` of score tracks, then the
`LabelFrame` containing the actual human-confirmation mapping controls last.
Every shell layer built on top of `DesktopApp` (`GuidedDesktopApp`'s "Song
progress" readiness banner, `ProductDesktopApp`'s Song Workspace bar,
`LiveDiagnosticsGuidedDesktopApp`'s "Live diagnostics" panel) inserts another
fixed-height frame above the notebook, so the packaged shell can leave the
notebook very little vertical room. Because the mapping controls were the
*last* thing packed in the tab and the tab had no scrollbar, a short notebook
area clipped them below the visible area with no way to reach them.

## Fix

- Build the "Human-confirmed Rocksmith arrangement mappings" `LabelFrame`
  immediately after the tab header, before the track table, so the actual
  gate action always renders directly under the header regardless of how
  little vertical room the notebook has.
- Move the (informational, non-blocking) track `Treeview` into its own frame
  paired with a vertical `ttk.Scrollbar`, so every track row stays reachable
  even when the tab is short, without depending on the whole tab area.

## Regression protection

`tests/test_desktop_score_tab_layout.py` exercises the real
`DesktopApp._build_layout` source against lightweight recording stand-ins for
the `ttk`/`tk` widget classes (no live Tk root or display required, matching
this repository's existing no-display GUI test convention). It asserts that
the mapping `LabelFrame` is built before the track-table frame within
`score_tab`, and that the track `Treeview` has a working vertical scrollbar
wired to it. Reverting the build order or dropping the scrollbar wiring fails
both tests.

## Residual risk

No automated screenshot of the real desktop application was taken; this
mirrors the project's own CI, which does not render/screenshot this GUI on
any platform. A packaged-app retest of the same representative project should
confirm the mapping controls are now visible immediately under the Score &
Mappings header on the same 1600x960 viewport before this finding is
considered closed. Other tabs (Rights / Provenance, Activity Log) were not
audited for the same class of clipping in this pass; if a similar report
surfaces for another tab, cross-link it here rather than treating it as
unrelated.
