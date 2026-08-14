# Project score registration

A complete MusicXML/MXL or Guitar Pro 3-5 score can now be registered once under a CDLC project before arrangement-specific extraction.

## Behavior

Registration stores an immutable-by-hash local copy under `sources/score/original/` and writes the whole-score `ProjectScoreSource` inventory to `sources/score/source.json`.

The inventory keeps every discovered part/track and any proposed Bass, Lead, and Rhythm mapping from the shared score inventory layer. Importer proposals remain `human_confirmed=false`; registration does not accept a role assignment or bypass musical review.

The score registration also writes a source intake receipt with the supplied rights classification. Unknown rights remain human-review-required. `streaming_reference_only` material cannot be registered as local score bytes.

Registering the same score bytes again is idempotent even if the input file has been renamed. The existing stored source path, intake receipt, inventory, and any later human-confirmed arrangement mappings are preserved rather than rebuilt from importer proposals. Registering a different score into a project that already has one is refused until an explicit replacement workflow exists, preventing silent source substitution.

## `cdlc-draft` integration

When `cdlc-draft` receives a supported complete score, it now registers the whole score before running the existing Bass-specific notation import. This is transitional compatibility behavior: Bass remains the current proving path, while the project retains the complete source inventory needed for later Lead/Rhythm fan-out.

If Bass extraction is ambiguous and stops for `--track-index`/human selection, the project-level score inventory has already been preserved. No Bass/Lead/Rhythm proposal is automatically confirmed by that registration.

MIDI and PSARC notation continue through their existing paths and are not claimed as complete shared-score registration in this slice.

## Safety boundary

- local symbolic score files only;
- project data remains under the gitignored `projects/` tree;
- no streaming/download/ripping behavior;
- no source-rights elevation;
- no automatic arrangement-role acceptance;
- no tone/fingering/musical correctness gate bypass;
- no live Rocksmith installation or NoCableLauncher modification.
