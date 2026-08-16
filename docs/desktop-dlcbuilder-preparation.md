# Desktop DLC Builder project preparation

The desktop build flow can now prepare the project-local DLC Builder `.rs2dlc` input without requiring PowerShell.

## Product path

`Workspace → DLC Builder Preparation…` exposes the existing deterministic `prepare_dlcbuilder_project` engine through the packaged application. The user may set the preview start and optionally override the DLC key, then request preparation.

Preparation remains validation-gated. It requires the configured Bass, Lead, and Rhythm arrangements to be ready, current Rocksmith XML exports to exist, normalized project audio to exist, and confirmed package metadata/cover authority to resolve successfully. The existing engine creates the private preview WAV and `.rs2dlc` data beneath `build/dlcbuilder/`.

## Safety and authority boundary

This surface does not:

- approve musical notes, timing, fingering, techniques, tones, source rights, or package readiness;
- weaken or bypass arrangement validation;
- launch DLC Builder yet;
- build or register a PSARC;
- copy generated package data into the repository;
- modify Rocksmith, its DLC directory, or NoCableLauncher.

Preparation work is project-bound asynchronous work. If the user changes projects before completion, the stale operation may release the global busy flag but cannot update the newly opened project's UI, show stale errors there, refresh it, or publish feature callbacks into it.

Executable discovery and explicit DLC Builder launch remain the next separate desktop-build slice so external-tool execution can be reviewed and tested independently from preparation authority.
