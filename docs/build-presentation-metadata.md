# Desktop metadata and cover authority

The desktop build flow has a project-bound presentation contract for package-facing album metadata and cover art.

## Product behavior

From the packaged desktop app, open **Workspace → Metadata & Cover…** for the current project. The surface lets the user review or enter:

- album name;
- release year;
- one local PNG or JPEG cover image.

If reviewed recording context contains one unambiguous album and release year, those values may be prefilled as suggestions. They do not become package presentation authority until the user explicitly confirms the form together with cover art.

Confirmation writes `metadata/build_presentation.json` and copies the selected image into `assets/cover.<ext>` inside the local project. The contract stores the cover SHA-256 and the loader re-verifies those exact bytes before later package preparation.

## Package invalidation

Album name, year, and cover art affect the package. If any confirmed value or cover bytes change, the package generation is advanced **before** replacement data is published. Existing `build/dlcbuilder` and `build/staging` state is removed through the shared package-generation invalidation path.

Re-confirming the same normalized album/year and byte-identical cover is a no-op and does not advance package generation.

`prepare_dlcbuilder_project()` now uses the saved presentation as defaults when album, year, or cover are not supplied explicitly. Existing explicit CLI inputs remain supported and take precedence.

## Safety and authority boundaries

This contract owns package presentation only. It does not approve or alter:

- source rights or provenance;
- Bass/Lead/Rhythm score mappings;
- timing, notes, positions, fingering, techniques, chord identity, or tones;
- validation or Rocksmith XML readiness;
- PSARC readiness or integrity;
- live Rocksmith installation or NoCableLauncher configuration.

Cover art remains private local project data. The application does not download artwork, does not add commercial media to the repository, and does not treat metadata confidence as human approval.
