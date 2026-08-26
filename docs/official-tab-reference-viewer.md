# Official TAB Reference Viewer

Related: #433

## Purpose

The Official TAB Reference Viewer makes privately owned photographed/scanned tablature useful during Song Workspace authoring without committing copyrighted page images to the public repository and without making image content automatic musical authority.

The first implementation is deliberately **reference-first, not OCR-first**:

```text
local JPG/PNG page
    ↓
copy into the song project's private reference directory
    ↓
SHA-256 provenance registration
    ↓
map page to Bass / Lead / Rhythm + score-bar range
    ↓
shared score measure → promoted recording clock
    ↓
Arrangement Preview follows the applicable page while playback moves
```

OCR/OMR and automatic score disagreement detection remain a later layer. This keeps the first viewer useful immediately while preserving a stable provenance and mapping contract for recognition to build on.

## Local project layout

Registered pages are copied under the user's song project:

```text
<song-project>/
  references/
    official-tab/
      manifest.json
      pages/
        <sha-prefix>-<original-name>.jpg
        ...
```

These files are local project evidence. They are not repository fixtures and must not be committed to this public repository. Automated repository tests generate synthetic images only.

## Manifest authority

`references/official-tab/manifest.json` records:

- immutable page SHA-256;
- project-relative image path;
- optional printed page label;
- arrangement role (`bass`, `lead`, `rhythm`);
- inclusive score-bar range;
- normalized image bounding box for the mapped region.

The first UI maps the whole page (`0,0,1,1`). The bounding-box field exists now so a later graphical system/measure region mapper can narrow exact page regions without replacing the provenance model.

Mappings for the same arrangement may not overlap. A bar therefore resolves to at most one official-reference region. Invalid, overlapping, missing, path-escaping, unsupported-format, or hash-changed references fail closed.

## Arrangement Preview behavior

The EOF/Rocksmith-inspired live preview retains its 2D string lanes. The lower pane can toggle between:

- the existing perspective highway; and
- **Official TAB reference**.

When a registered page is available:

1. Arrangement Preview selects the current Bass/Lead/Rhythm role.
2. The current shared-clock playhead resolves to a score bar through the existing `MeasureWindow` model.
3. The official-reference manifest selects the page/range that covers that score bar.
4. The page is rendered from the private project copy and its registered SHA is rechecked.
5. The mapped page region is outlined and the current bar/range is displayed.

The reference viewer supports fit-width rendering, zoom, scroll, previous/next mapped page navigation, and seek-to-page-start. Changing page/role or seeking uses the existing authoritative shared recording clock; no independent image timing offset exists.

## Adding a page

From Arrangement Preview choose **Show Official TAB** and **Add page…**.

The dialog asks for:

- arrangement role;
- first score bar;
- last score bar;
- optional printed page label.

The selected JPG/JPEG/PNG is decoded before registration, copied into the project, hashed, and then added to the manifest. The copied local image remains private project evidence.

Removing a mapping removes only the manifest mapping. The private copied image intentionally remains on disk so a UI action cannot silently destroy the user's source evidence.

## Safety / authority boundaries

Viewing or navigating official TAB does **not**:

- rewrite the Guitar Pro/MusicXML import;
- modify source events;
- change shared timing;
- accept string/fret placement;
- clear review findings;
- change validation state;
- make a package export-ready.

This viewer is evidence and navigation only. Later OCR/OMR can derive candidate events from the same image provenance, but recognized events must remain confidence-aware and human-reviewable as specified in `printed-notation-tab-practice-mode.md`.

## Acceptance coverage

Automated tests cover:

- private image copy + SHA registration;
- arrangement/bar lookup;
- hash-change rejection;
- project path containment;
- same-arrangement overlap rejection;
- score-bar to shared-clock seek resolution.

Packaged Product Reality testing should additionally verify that a real private page can be imported and remains synchronized while the user plays/seeks through mapped bars.