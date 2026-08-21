# Desktop UI audit (#305, deliverable 1 of many)

This is the first #305 deliverable only: "a short UI/UX audit ... of the current
application" (`PROJECT_PLAN.md`'s evidence-driven slice order is *UI audit →
design-system foundation → highest-value workflow surfaces → regression/smoke
coverage*). It does not change or retrofit any screen — see
`docs/ui/design-system-foundation.md` for the tokens this audit motivates, and
`PROJECT_PLAN.md` for why "Updated primary Windows workflow screens" is a later,
separate slice.

## How this audit was performed, and why

The product's stated primary platform is a packaged **Windows 11 desktop
application** (`docs/project-status.yaml` → `product.primary_platform`). The
technology stack is **Python + `tkinter`/`ttk`** (stdlib), not a web/Electron
front end and not a native `.NET` WPF/WinForms app — a repo-wide search found no
`.csproj`, `.xaml`, `.sln`, or `package.json`, and every `*_ui.py` / `desktop_*.py`
/ `*_window.py` module imports `tkinter`.

That matters for how this audit could be produced here:

- This is a Linux cloud sandbox with no Windows and, ordinarily, no display
  server. `tkinter`'s Tk/Tcl bindings were not even installed on the Linux
  Python normally available in this environment.
- For due diligence, `python3-tk` and `Xvfb` were installed manually in this
  sandbox and a real, live `tk.Tk()` root plus `ttk.Style` *were* successfully
  constructed and exercised headlessly (see
  `docs/ui/design-system-foundation.md` for that verification). So a live
  render is not fundamentally impossible here.
- However, the project's own CI (`.github/workflows/ci.yml`, `ubuntu-latest`)
  does **not** install `python3-tk` or attempt any GUI instantiation — it only
  imports and runs the pure-Python layers. GUI import/build verification is
  exclusively done by the separate, Windows-only `.github/workflows/windows-desktop.yml`
  job, and even that job only import-checks the modules and runs PyInstaller —
  it never renders or screenshots a window. There is **no rendering-based UI
  test precedent anywhere in this repository, on any platform.**
- Rendering the actual application windows meaningfully would additionally
  require the `audio`/`guitarpro` desktop extras (not part of this task's
  `.[dev,beat]` install), `sounddevice` against real/virtual audio hardware,
  and a populated project directory with a registered score and source
  recordings — none of which exist in this sandbox, and fabricating them
  would produce screenshots of an unrepresentative, effectively-empty UI.

Given that, this audit is a **static code-inventory review**: every
`*_ui.py`, `desktop_*.py`, and `*_window.py` module was read directly, and
component/style usage was catalogued with repository-wide search across the
full source. **No screenshots were taken and none are claimed here or in the
design-system document** — where a value below could not be confirmed by
reading the code, it is stated as unconfirmed rather than guessed.

## Screen/window inventory

The desktop app is organized as one main shell (`desktop_app.DesktopApp`,
extended by `desktop_shell.ProductDesktopApp`) that opens additional
`tk.Toplevel` windows on demand from its `Workspace` menu. 30 distinct
`*_ui.py` / `*_window.py` / `desktop_*.py` modules exist; the following own a
`tk.Toplevel` subclass (i.e. are their own top-level window rather than a
panel embedded in Song Workspace):

| Module | Window | Purpose |
| --- | --- | --- |
| `desktop_app.py` | `DesktopApp` (root `Tk`) | Project manager / main shell |
| `song_workspace_ui.py` | Song Workspace | Primary authoring surface — hosts most panels below as tabs/frames |
| `product_reality_ui.py` | Product Reality Gate Recorder | Manual evidence-run recorder |
| `metadata_cover_window.py` | Metadata & Cover | Metadata + cover art editing |
| `tone_regions_window.py` | Tones & Regions | Tone region authoring |
| `desktop_xml_export_window.py` | Rocksmith XML Export | XML export controls |
| `desktop_dlcbuilder_window.py` | DLC Builder Handoff | DLC Builder staging/launch |

Panels embedded inside Song Workspace (not separate windows) include, among
others: `validation_dashboard_ui.py` (Bass/Lead/Rhythm validation dashboard),
`eof_workspace_ui.py` (Editor on Fire reference — this is where #339's
hand-position evidence now surfaces), `track_trust_workspace_ui.py`,
`review_queue_workspace_ui.py`, `score_role_composition_workspace_ui.py`,
`timing_bpm_workspace_ui.py`, `song_workspace_playback_ui.py`, plus the
editing panels `arrangement_edit_history_ui.py`,
`arrangement_event_selection_ui.py`, `arrangement_event_timing_ui.py`,
`arrangement_preview_ui.py`, `arrangement_technique_ui.py`,
`audio_output_ui.py`, `chord_fingering_ui.py`, `chord_identity_ui.py`,
`timing_review_ui.py`.

## Component inventory (repo-wide widget usage counts)

Counted directly from source across all `*_ui.py` / `desktop_*.py` /
`*_window.py` / `*_shell.py` files:

| Widget | Occurrences |
| --- | --- |
| `ttk.Label` | 118 |
| `tk.StringVar` | 92 |
| `ttk.Button` | 75 |
| `ttk.Frame` | 63 |
| `ttk.LabelFrame` | 32 |
| `ttk.Combobox` | 15 |
| `ttk.Entry` | 14 |
| `ttk.Treeview` | 6 |
| `tk.Text` | 6 |
| `tk.Menu` | 6 |
| `ttk.Notebook` | 5 |
| `ttk.Spinbox` | 4 |
| `ttk.Separator` | 4 |
| `tk.Canvas` | 4 |
| `ttk.Progressbar` | 3 |
| `ttk.Checkbutton` | 3 |
| `ttk.Scale` | 2 |
| `ttk.Panedwindow` | 2 |
| `tk.Toplevel` (direct, outside a named subclass) | 1 |

Reusable, first-class controls exist for the primitives above via `ttk`, but
there is **no shared, named composite control** anywhere in the codebase for
recurring authoring-UI patterns — every screen builds its own status label,
its own "role" (Bass/Lead/Rhythm) row, and its own button bar layout from
scratch using the primitives above.

## Findings

1. **No design-system layer exists today.** A repo-wide search for
   `ttk.Style(` found **zero** matches prior to this pass (the only match now
   is this pass's own new `design_tokens.py`, described below). No existing
   screen configures a named ttk style, a theme, or a shared palette; every
   widget uses ttk's unstyled defaults except where a literal `font=(...)`
   tuple is passed inline.
2. **Status is communicated as plain, unstyled text only.** Strings like
   `"PASS"`, `"FAIL"`, `"WARNING"` appear in over a dozen places (dashboard,
   validation, EOF, track-trust, review-queue panels) as literal Python
   strings, always rendered through a plain `ttk.Label`/`Treeview` cell with
   no color, weight, or icon differentiation. This means status *text*
   already avoids "color alone" by accident, but it also means nothing helps
   a user visually scan a busy panel for the FAIL rows — every status looks
   identical regardless of severity, and a stale value is indistinguishable
   from a fresh one.
3. **Typography is inconsistent and mostly unset.** Only 8 call sites across
   the whole UI layer pass an explicit `font=` tuple, and they use only three
   sizes (10, 11, 18pt "Segoe UI", plain or bold) with no naming/semantics —
   each call site re-derives what a heading or a title should look like.
   Every other label falls back to whatever the Tk default font happens to
   be, so there is no deliberate typographic hierarchy.
4. **Spacing is ad hoc.** `padx=`/`pady=` values in the audited files include
   2, 4, 5, 6, 7, 8, 10, 12, and 14 (px), often as bare integers or
   inconsistent 2-tuples, with no evident grid. Visual rhythm between panels
   varies screen to screen.
5. **No icon system.** No image/icon assets or icon font usage were found;
   any future icon/symbol needs (including the semantic status glyphs added
   in this pass) currently have to be plain Unicode glyphs in label text
   rather than a bitmap/vector icon set.
6. **Menu/window structure is consistent, if minimal.** The `Workspace` menu
   pattern in `desktop_shell.py` (open/refresh Song Workspace, then a
   consistent set of `…` — ellipsis — labeled window-opening commands) is a
   good existing convention worth keeping and formalizing rather than
   replacing.
7. **Provenance/safety text is already a strong, consistent convention.**
   Nearly every panel explicitly states in plain text what it does *not* do
   (e.g. "does not accept fingering or playability", "does not change project
   authority") — this is a real, valuable existing pattern for human review
   gates and should be preserved verbatim as UI work continues, not
   redesigned away for visual polish.

## What this motivates (delivered in this pass)

`docs/ui/design-system-foundation.md` and
`src/rocksmith_cdlc_generator/design_tokens.py` define a minimal typography
scale, a 4px spacing scale, and a semantic status-style registry
(PASS/WARNING/FAIL/STALE/REVIEW REQUIRED/INFO) that pairs color with a symbol
and label text so status is never color-alone, with STALE additionally
italicized so it stays visually unmistakable. That module is *not* yet wired
into any existing screen — adoption in real windows is explicitly the next,
separate #305 slice ("highest-value workflow surfaces"), not this one.

## What was not done, and why

- **No screenshots.** As explained above, a meaningful, representative
  screenshot would require desktop extras and fixture project data this pass
  did not build, and the project's own CI never does this either. Claiming a
  screenshot without one would be worse than not having one.
- **No screen changes.** Adopting the new tokens in `song_workspace_ui.py`
  and the other screens above is deliberately left for the next #305 slice so
  this stays a small, reviewable step and does not risk masking or changing
  behavior of any functional (#304) or provenance/review-gate logic.
- **No icon asset set.** Establishing icon conventions was named in #305's
  first deliverable; this pass only notes the current gap (no icons at all)
  and reuses plain Unicode glyphs for the new status tokens as an interim,
  zero-asset approach. A real icon set is left as future scope.
