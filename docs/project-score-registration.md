# Project score registration

A complete MusicXML/MXL or Guitar Pro 3-5 score can now be registered once under a CDLC project before arrangement-specific extraction.

## Behavior

Registration stores an immutable-by-hash local copy under `sources/score/original/` and writes the whole-score `ProjectScoreSource` inventory to `sources/score/source.json`.

The inventory keeps every discovered part/track and any proposed Bass, Lead, and Rhythm mapping from the shared score inventory layer. Importer proposals remain `human_confirmed=false`; registration does not accept a role assignment or bypass musical review.

The score registration also writes a source intake receipt with the supplied rights classification. Unknown rights remain human-review-required. `streaming_reference_only` material cannot be registered as local score bytes.

Registering the same score bytes again is idempotent even if the input file has been renamed. The existing stored source path, intake receipt, inventory, and any later human-confirmed arrangement mappings are preserved rather than rebuilt from importer proposals. Registering a different score into a project that already has one is refused outright: there is currently no in-app or CLI workflow to replace an already-registered score, so the refusal message tells the user to start a new project with the corrected file rather than implying a replacement path exists (#304). This is deliberate, not an oversight -- Bass/Lead/Rhythm mappings, shared timing, fan-out, and drafts are all bound to this score's bytes, and silently substituting them mid-project is the same stale-authority failure mode #193 tracks.

## Human mapping review

`cdlc-score-map PROJECT show` displays the registered whole-score inventory and current Bass/Lead/Rhythm mapping state after first verifying that the stored score bytes still match the project contract.

`cdlc-score-map PROJECT confirm ROLE TRACK_INDEX` is the explicit human acceptance step for one arrangement role. Confirming the importer's proposed track preserves its confidence and evidence. Choosing a different known track records the human selection without inventing importer confidence. No mapping is accepted merely because its proposal confidence is high.

Mapping review refuses to proceed if the registered source bytes are missing or no longer match their recorded SHA-256, so a human decision cannot silently attach to substituted score content.

Concurrent mapping confirmations are serialized with an operating-system file lock and each replacement uses a unique same-directory temporary file. Successful confirmations for different roles therefore cannot overwrite one another with stale score-contract snapshots. Atomic replacement also preserves the existing contract's permission bits and, on POSIX, its group ownership so a confirmation does not silently remove access from a shared project. If the operating system refuses preservation of the original group, the confirmation fails before replacing the contract.

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
