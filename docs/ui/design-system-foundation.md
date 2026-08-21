# Desktop design-system foundation (#305, deliverable 1 of many)

This is the second half of #305's first deliverable: "a small design-system
foundation: typography, spacing, semantic status styles, reusable controls,
layout rules, and icon conventions." It is implemented as real, tested code in
`src/rocksmith_cdlc_generator/design_tokens.py`, motivated by the findings in
`docs/ui/desktop-ui-audit.md`. Read that document first for *why* each token
below exists.

**Scope of this pass:** tokens only. No existing screen has been changed to
adopt them — see "What adoption looks like" below and `PROJECT_PLAN.md`'s
evidence-driven #305 slice order (*UI audit → design-system foundation →
highest-value workflow surfaces → regression/smoke coverage*). This pass does
not touch, weaken, or reinterpret any provenance, validation, review-gate, or
Bass/Lead/Rhythm-parity logic; the tokens are pure presentation.

## Why code, not just a spec

The codebase already separates pure-Python "status" modules (e.g.
`validation_dashboard.py`) from their `tkinter` UI wrapper (e.g.
`validation_dashboard_ui.py`), and tests only exercise the pure layer — no
test in this repository instantiates a live `tk.Tk()` root, and the project's
own Linux CI does not install `tkinter` at all. `design_tokens.py` follows
that same convention: the token data (`TypeStyle`, `StatusStyle`, the
typography/spacing/status registries) is plain `pydantic` data with no
`tkinter` import, so it type-checks, imports, and is unit-tested exactly like
any other module under `pytest -q` — no display server required, and nothing
about it can break the existing CI.

## Typography scale

One named scale (`TYPOGRAPHY` in `design_tokens.py`), all on the "Segoe UI"
family already used in the app (`FONT_FAMILY`):

| Name | Size | Weight | Existing usage this formalizes |
| --- | --- | --- | --- |
| `display` | 18pt | bold | Window/panel titles (already used, ad hoc) |
| `heading` | 13pt | bold | *New* — section headings; no prior consistent equivalent |
| `subheading` | 11pt | bold | Sub-section/summary lines (already used, ad hoc) |
| `body` | 10pt | normal | Default body text (already the most common explicit size) |
| `body_bold` | 10pt | bold | Emphasized body text at body size |
| `caption` | 9pt | normal | *New* — secondary/help/timestamp text |

`TypeStyle.as_tuple()` returns the exact `("Segoe UI", size)` /
`("Segoe UI", size, "bold")` / `("Segoe UI", size, "bold italic")` shape
`tkinter`/`ttk` widgets accept as `font=`, so adoption is a drop-in
`font=TYPOGRAPHY["heading"].as_tuple()` at any call site.

## Spacing scale

A single 4px base unit (`SPACING_UNIT_PX`), with named multiples via
`spacing(name)`:

| Name | Multiple | Pixels |
| --- | --- | --- |
| `xs` | ×1 | 4px |
| `sm` | ×2 | 8px |
| `md` | ×3 | 12px |
| `lg` | ×4 | 16px |
| `xl` | ×6 | 24px |

This replaces the ad hoc `padx=`/`pady=` values found across the audit (2, 4,
5, 6, 7, 8, 10, 12, 14px) with a single small scale that covers the same
practical range (4–24px) without inventing a new value per screen.

## Semantic status styles — never color alone

`STATUS_STYLES` defines six semantic states: `pass`, `warning`, `fail`,
`stale`, `review_required`, `info`. Every state pairs three channels so no
status is ever conveyed by color alone (the explicit #305 requirement, and
consistent with how "PASS"/"FAIL"/"WARNING" are already plain, readable
strings everywhere in this codebase today):

1. a distinct **symbol** (e.g. `✓`, `✗`, `⚠`, `⏳`, `◉`, `ℹ`),
2. **label text** (`"PASS"`, `"FAIL"`, `"WARNING"`, `"STALE"`,
   `"REVIEW REQUIRED"`, `"INFO"`),
3. a **foreground color**, chosen for contrast on ttk's default light
   Windows themes.

`StatusStyle.format(detail=None)` composes `"✗ FAIL — 97 unmapped notes"` —
meaning the text alone (with no color/font applied at all) already fully
communicates the state, which matters for plain-text contexts like log lines
or accessibility tooling that ignore styling entirely.

`STALE` is additionally rendered **italic** (`slant="italic"`) as a second,
color-independent signal, so a stale value stays visually unmistakable even
for a viewer who cannot distinguish the color at all — directly addressing
#305's "stale/invalid must be visually unmistakable" requirement, and
matching this project's existing fail-closed treatment of stale evidence
(e.g. the EOF hand-position status surfaced by #339).

| State | Symbol | Label | Foreground | Slant |
| --- | --- | --- | --- | --- |
| `pass` | ✓ | PASS | `#1B5E20` | roman |
| `warning` | ⚠ | WARNING | `#8A5B00` | roman |
| `fail` | ✗ | FAIL | `#B3261E` | roman |
| `stale` | ⏳ | STALE | `#5C5C5C` | *italic* |
| `review_required` | ◉ | REVIEW REQUIRED | `#3F51B5` | roman |
| `info` | ℹ | INFO | `#37474F` | roman |

`configure_ttk_status_styles(style)` registers each state as a named
`ttk.Style` (`Status.Pass.TLabel`, `Status.Fail.TLabel`, ...) so a widget can
opt in with `ttk.Label(parent, text=..., style="Status.Fail.TLabel")`. It
takes the live `ttk.Style` as a loosely-typed `object` specifically so
importing `design_tokens` never requires `tkinter` to be present (see "Why
code, not just a spec" above).

### Icon conventions (interim)

No icon/image asset system exists in the app today (the audit found none).
This pass reuses plain Unicode glyphs for the six status symbols above as a
zero-asset interim convention — they render with any font, need no build
step, and are already legible at 10pt in the "Segoe UI" body size. A real
bitmap/vector icon set (toolbar/menu icons, arrangement-role icons, etc.) is
out of scope for this deliverable and is left for a later #305 slice.

### Reusable controls / layout rules (status of this deliverable)

#305's first deliverable also names "reusable controls" and "layout rules."
This pass deliberately stops at *tokens* (typography, spacing, semantic
status) rather than shipping new composite widget classes or a layout grid
system, because:

- no existing screen has adopted the tokens yet, so a composite control built
  before any real adoption risks guessing the wrong shape;
- `PROJECT_PLAN.md` explicitly sequences "highest-value workflow surfaces" as
  the *next* slice, after the foundation — composite controls are better
  designed against that real adoption work than speculatively now.

The typography/spacing scale above **is** the layout-rule foundation
(consistent spacing units, a defined type scale) that composite controls and
screen updates in the next slice should build on.

## Verification performed

- `python -m compileall -q src tests` — passes, including the new module and
  test file.
- `python -m pytest -q tests/test_design_tokens.py` — 10/10 tests pass. Tests
  cover: the typography scale uses the shared font family and strictly
  increasing sizes; the spacing scale is a strictly increasing, consistent
  multiple of the base unit; every status has a unique label and symbol;
  every status's formatted text carries its meaning without color; `stale` is
  the only state rendered italic; `TypeStyle.as_tuple()` produces the exact
  tuple shape `tkinter` expects; and `configure_ttk_status_styles` calls
  `.configure(...)` exactly once per status with `foreground`/`font` set,
  verified against a fake `ttk.Style` stand-in so the test needs no display
  server.
- **Manual, one-time sandbox verification against a real, live `ttk.Style`**
  (not part of the automated suite, and not something the project's CI does):
  after installing `python3-tk` and running under `xvfb-run` in this sandbox
  only, a real `tk.Tk()` root and `ttk.Style(root)` were constructed,
  `configure_ttk_status_styles(style)` was called, and `style.lookup(...)`
  was read back for every status to confirm the foreground color and font
  tuple were actually applied by real Tk/Tcl — not just accepted by a mock.
  Output (foreground, font):

  ```text
  Status.Pass.TLabel          -> #1B5E20   Segoe UI 10 bold
  Status.Warning.TLabel       -> #8A5B00   Segoe UI 10 bold
  Status.Fail.TLabel          -> #B3261E   Segoe UI 10 bold
  Status.Stale.TLabel         -> #5C5C5C   Segoe UI 10 bold italic
  Status.ReviewRequired.TLabel-> #3F51B5   Segoe UI 10 bold
  Status.Info.TLabel          -> #37474F   Segoe UI 10
  ```

  This is genuine evidence the styling code works against real Tk, but it
  used tooling (`python3-tk`, `Xvfb`) not present in this project's normal
  dev/CI image, so it is **not** repeatable by CI and is not claimed as an
  automated check. No screenshot was taken or is claimed — this was a
  programmatic style-lookup check, not a visual/pixel verification.

## What adoption looks like (explicitly not done in this pass)

A future, separate #305 slice should retrofit real screens to import from
`design_tokens` instead of inline literals — for example,
`validation_dashboard_ui.py`'s `font=("Segoe UI", 11, "bold")` becoming
`font=TYPOGRAPHY["subheading"].as_tuple()`, and its `Treeview` "validation"
column values (currently plain `"PASS"`/`"FAIL"`/`"WARNING"` strings) using
`format_status(...)` and/or a `configure_ttk_status_styles`-registered style
per row. That adoption work — and any accompanying screenshot/interaction
testing — is intentionally left for that later slice so this one stays small,
reviewable, and incapable of masking a functional defect behind a visual
change.
