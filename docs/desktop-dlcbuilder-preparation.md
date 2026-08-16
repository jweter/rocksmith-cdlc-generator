# Desktop DLC Builder handoff

The desktop build flow can prepare the project-local DLC Builder `.rs2dlc` input and explicitly launch DLC Builder without requiring PowerShell.

## Product path

`Workspace → DLC Builder Handoff…` exposes the existing deterministic `prepare_dlcbuilder_project` engine through the packaged application. The user may set the preview start and optionally override the DLC key, then request preparation.

Preparation remains validation-gated. It requires the configured Bass, Lead, and Rhythm arrangements to be ready, current Rocksmith XML exports to exist, normalized project audio to exist, and confirmed package metadata/cover authority to resolve successfully. The existing engine creates the private preview WAV and `.rs2dlc` data beneath `build/dlcbuilder/`.

The same window can resolve the external DLC Builder executable from the explicit `ROCKSMITH_DLCBUILDER_EXE` environment variable or `PATH`, or the user can choose the executable with **Browse…**. Discovery does not scan Rocksmith directories or arbitrary disks.

Launching is always a separate explicit user action. **Launch DLC Builder** reuses the existing `launch_dlcbuilder` engine, which first stages the current `.rs2dlc` and all referenced assets through the package-readiness gate and only then starts the selected external executable with the current project file.

## Form-state correctness

The preparation form is project-scoped UI state. When the window is reused for a different project, preview position and DLC-key override return to their neutral defaults before the new project can be prepared. Refreshing the same project preserves unsaved form edits. The executable selection is tool-level state rather than project authority and may remain selected across project switches.

Preview start accepts only finite, non-negative seconds. `NaN`, positive infinity, and negative infinity are rejected in the form instead of being forwarded to FFmpeg or the package-preparation engine.

## Safety and authority boundary

This surface does not:

- approve musical notes, timing, fingering, techniques, tones, source rights, or package readiness;
- weaken or bypass arrangement validation or build staging;
- build, register, install, or copy a PSARC;
- copy generated package data into the repository;
- modify Rocksmith, its DLC directory, player profile, or NoCableLauncher;
- silently launch an external tool during preparation, refresh, discovery, or project open.

Preparation and launch requests are project-bound asynchronous work. If the user changes projects before completion, stale completion cannot update the newly opened project's UI, show stale errors there, refresh it, or publish feature callbacks into it.

DLC Builder remains responsible for WEM/SNG/manifest/PSARC construction. Returned PSARC registration and integrity verification remain a separate explicit desktop-build step.
