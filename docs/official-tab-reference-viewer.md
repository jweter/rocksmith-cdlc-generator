# Official TAB Reference Viewer

Related: #433, #435

## Purpose

The Official TAB Reference Viewer makes privately owned photographed/scanned tablature useful during Song Workspace authoring without committing copyrighted page images to the public repository and without making image content automatic musical authority.

The implementation is deliberately **reference-first, not OCR-first**:

```text
local JPG/PNG page
    ↓
copy into the song project's private reference directory
    ↓
SHA-256 provenance registration
    ↓
map the same page to any applicable Bass / Lead / Rhythm roles + score-bar range
    ↓
shared score measure → promoted recording clock
    ↓
Arrangement Preview follows the applicable page while playback moves
```

OCR/OMR and automatic score disagreement detection remain a later layer. This keeps the viewer useful immediately while preserving a stable provenance and mapping contract for recognition to build on.

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

When one printed page contains material for more than one arrangement, the image is copied **once**. Its immutable page record then carries one mapping per selected arrangement. The user does not need to import an identical photograph separately for Bass, Lead, and Rhythm.

## Manifest authority

`references/official-tab/manifest.json` records:

- immutable page SHA-256;
- project-relative image path;
- optional printed page label;
- one or more arrangement mappings (`bass`, `lead`, `rhythm`);
- inclusive score-bar range for each mapping;
- normalized image bounding box for the mapped region.

The current UI maps the whole page (`0,0,1,1`). The bounding-box field exists now so a later graphical system/measure region mapper can narrow exact page regions without replacing the provenance model.

Mappings for the same arrangement may not overlap. The same page may legitimately carry overlapping bar ranges **across different arrangements** because each role is resolved independently. A bar therefore resolves to at most one official-reference region for the selected arrangement. Invalid, same-role overlapping, missing, path-escaping, unsupported-format, or hash-changed references fail closed.

## Arrangement Preview behavior

The EOF/Rocksmith-inspired live preview retains its 2D string lanes. The lower pane can toggle between:

- the existing perspective highway; and
- **Official TAB reference**.

When a registered page is available:

1. Arrangement Preview selects the current Bass/Lead/Rhythm role.
2. The current shared-clock playhead resolves to a score bar through the existing `MeasureWindow` model.
3. The official-reference manifest selects the page/range that covers that score bar for the selected role.
4. The page is rendered from the private project copy and its registered SHA is rechecked.
5. The mapped page region is outlined and the current bar/range is displayed.

The reference viewer supports fit-width rendering, zoom, scroll, previous/next mapped page navigation, and seek-to-page-start. Changing page/role or seeking uses the existing authoritative shared recording clock; no independent image timing offset exists.

## Adding a page

From Arrangement Preview choose **Show Official TAB** and **Add page…**.

The dialog asks for:

- every arrangement shown on the page, using independent Bass / Lead / Rhythm checkboxes;
- first score bar;
- last score bar;
- optional printed page label.

At least one arrangement must be selected. The currently viewed arrangement is selected by default, but the user can choose any combination. Before registration, the UI rejects a proposed range that would overlap an existing mapping for any selected arrangement. Cross-arrangement overlap is valid.

The selected JPG/JPEG/PNG is decoded before registration, copied into the project once, hashed, and then associated with one deterministic mapping for each selected arrangement. The copied local image remains private project evidence.

Removing a mapping removes only that role/range mapping from the manifest. Other mappings on the same page remain intact, and the private copied image intentionally remains on disk so a UI action cannot silently destroy the user's source evidence.

## Safety / authority boundaries

Viewing, registering, or navigating official TAB does **not**:

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
- one private image shared by Bass, Lead, and Rhythm mappings without duplicate copies;
- arrangement/bar lookup for each role;
- hash-change rejection;
- project path containment;
- same-arrangement overlap rejection;
- score-bar to shared-clock seek resolution.

Packaged Product Reality testing should additionally verify that one real private page can be selected for multiple applicable arrangements in a single import, follows the correct page/bar when switching roles or seeking, and leaves musical/review authority unchanged.
