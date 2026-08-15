# Rocksmith CDLC Generator — Canonical Roadmap

This file is the canonical implementation roadmap for the project. The product goal is a real Windows desktop application that turns one local song recording plus one complete structured score, when available, into reviewed Rocksmith 2014 Bass, Lead, and Rhythm arrangements with as little manual authoring as practical.

The engine remains local-first, deterministic where possible, provenance-aware, and explicit about human review. The GUI is the primary product. The CLI is an engine/debugging interface, not the intended normal user experience.

## North-star workflow

```text
Launch Windows app
    ↓
Choose local song recording
    ↓
Choose complete Guitar Pro / MusicXML score
    ↓
Create song project
    ↓
Review rights/provenance
    ↓
Confirm Bass / Lead / Rhythm score mappings
    ↓
Analyze recording + fan out score tracks
    ↓
Align score to recording once
    ↓
Review/promote one shared song timeline
    ↓
Generate Bass + Lead + Rhythm drafts
    ↓
Review timing / notes / chords / fingering / techniques
    ↓
Validate all arrangements
    ↓
Review metadata / cover / tones
    ↓
Export Rocksmith XML + prepare DLC Builder project
    ↓
Build and verify PSARC
    ↓
Manual install by the user
```

## Product architecture

The project has two layers:

- **Core engine:** Python models, importers, alignment, reconciliation, mapping, validation, authoring export, packaging orchestration, tests, and provenance controls.
- **Windows desktop application:** the normal end-user workflow, centered on a persistent **Song Workspace**.

The Song Workspace is the product center. It should eventually allow a user to complete nearly the entire authoring process without PowerShell or manually opening generated JSON files.

The current desktop implementation uses Tk/ttk because it is already shipping as a packaged Windows application. A toolkit migration is not a roadmap goal by itself; change GUI technology only if a concrete product requirement cannot be met cleanly.

## Governing rules

1. Build the product continuously. Defects are recorded as GitHub Issues and do not hijack the roadmap unless they block the normal Windows workflow, create reproducible wrong output, or violate a hard safety boundary.
2. Source media and registered score bytes are immutable identities.
3. One complete score is a project-level musical source, not three independent imports.
4. Bass, Lead, and Rhythm inherit one reviewed score-to-recording timeline whenever the shared-score workflow is used.
5. Human confirmation remains required for uncertain rights/provenance, source mappings, timing acceptance, fingering/playability, tone acceptance, and package readiness.
6. Never invent unresolved guitar string/fret positions.
7. Never silently turn confidence into authority.
8. Never download/rip streaming-reference media.
9. Never modify the live Rocksmith installation or NoCableLauncher.
10. Never commit commercial audio, private user packages, CFSM exports, Ubisoft-derived content, or other private generated data.
11. Packaging remains validation-gated.
12. The main product metric is human editing time per finished song minute.

## Completed foundation

The following capabilities are already established and should be reused rather than rebuilt:

- project creation with immutable audio identity;
- FFmpeg normalization;
- beat/tempo analysis;
- Bass transcription and mapping;
- Guitar Pro 3–5 and MusicXML structured-score intake;
- project-level complete-score registration;
- explicit human Bass/Lead/Rhythm mapping confirmation;
- score fan-out to arrangement-specific normalized sources;
- one shared reviewed score-to-recording timeline;
- Lead and Rhythm draft generation from that shared timeline;
- validation/review artifacts;
- Rocksmith 2014 XML authoring paths;
- deterministic DLC Builder handoff/staging;
- local PSARC registration/verification;
- first Windows desktop workspace;
- GitHub Actions Windows build producing `RocksmithCDLCGenerator.exe`.

## Current milestone — Song Workspace v1

This is the active product milestone.

The workspace should turn the first desktop shell into a useful authoring application rather than a collection of command buttons.

### Required scope

- richer project header with artist/title/duration/source/score status;
- clear overall project progress and next recommended action;
- arrangement tabs for Bass, Lead, and Rhythm;
- per-arrangement readiness/validation status;
- score mapping overview with confirmed/unconfirmed states;
- review/problem navigator that surfaces blocking and warning items;
- source/provenance summary;
- shared-timeline status and timing confidence summary;
- activity/history view;
- useful actions placed next to the information they affect;
- desktop-first error messages that explain what the user should do next;
- preserve all existing human gates and safety boundaries.

### Strong nice-to-haves for this and following workspace iterations

- recent-project dashboard with health badges;
- drag/drop audio, score, cover art, PSARC, and DLC Builder inputs;
- waveform preview and moving playhead;
- click-to-seek, zoom, scrub, loop region, and slowed playback;
- variable-tempo metronome;
- beat-grid and shared-timeline visualization;
- low-confidence timing region highlighting;
- note/chord overlays for all arrangements;
- Rocksmith-style fretboard preview;
- unresolved fingering highlighting;
- chord/fingering editor;
- section/phrase markers;
- review queue with next/previous issue navigation;
- validation issue jump-to-location behavior;
- metadata editor for artist/title/album/year/cover/DLC key;
- tone research/audition workspace with explicit acceptance;
- export dashboard showing exactly why each arrangement is or is not ready;
- DLC Builder discovery, launch, and return status;
- diagnostics for FFmpeg, bridge, DLC Builder, audio devices, and dependencies;
- persistent settings, keyboard shortcuts, scalable UI, high-DPI support, and accessibility;
- cancellable background tasks and progress reporting;
- safe crash/diagnostic report export with private media excluded by default.

## Next milestone — Interactive timing and playback

After the Song Workspace structure is useful, build the first genuinely interactive authoring surface:

- waveform rendering from normalized audio;
- synchronized playback;
- moving playhead;
- beat/measure grid;
- current shared alignment anchors/regions;
- click-to-seek and loop selection;
- variable-tempo click;
- timing confidence diagnostics;
- explicit human promotion/acceptance of corrected timing.

The timing editor must preserve raw automatic analysis separately from reviewed corrections.

## Following milestone — Arrangement review/editing

Make Bass, Lead, and Rhythm editable in the same workspace:

- note/chord event overlays;
- timing correction;
- fret/string correction;
- chord template/fingering editing;
- tuning visibility/editor where supported;
- technique review;
- virtual fretboard;
- source-disagreement visualization;
- confidence and provenance display;
- direct navigation from validation flags to the affected event.

No unresolved or unverified physical guitar position may pass silently into export.

## Following milestone — Complete desktop build flow

Bring the rest of the existing engine into the GUI:

- validation for all arrangements;
- metadata and cover art;
- tones and tone regions;
- Rocksmith XML export;
- DLC Builder project preparation;
- tool-path discovery and diagnostics;
- DLC Builder launch;
- package staging and readiness view;
- returned PSARC registration and integrity verification.

Normal use should not require PowerShell.

## Following milestone — Installable release

Turn the CI-built application bundle into a practical release experience:

- stable versioning;
- branded application icon and metadata;
- release artifacts on GitHub;
- installer or similarly simple distribution mechanism;
- dependency/tool diagnostics on first launch;
- migration handling for user settings/projects;
- documented backup/recovery behavior;
- optional update notification only if it remains safe and unobtrusive.

## Later capability expansion

These are important, but they should not interrupt completion of the desktop authoring workflow:

- stronger audio-only transcription for songs without structured scores;
- additional Guitar Pro formats through safe adapters;
- richer technique detection;
- dynamic difficulty authoring controls;
- tone-region detection and Rocksmith device mapping;
- section/phrase inference;
- improved source reconciliation;
- batch/project-library tools;
- benchmark suite for real correction-time measurement;
- optional local AI assistance where it provides measurable editing-time reduction without weakening provenance or human gates.

## Issue policy

When development or Codex review finds an error:

- create/update a GitHub Issue with severity, reproduction context, and expected fix direction;
- continue the active product milestone by default;
- interrupt the roadmap only when the defect blocks the normal Windows desktop path, creates reproducible wrong output on that path, risks data loss, or violates a hard safety boundary;
- fix the accumulated backlog deliberately in later reliability/hardening passes.

This policy exists to prevent endless corrective micro-PR loops while still ensuring defects are never forgotten.

## Testing strategy

- deterministic unit tests for models/transforms/validators;
- integration tests across adjacent pipeline stages;
- Windows CI for the desktop and PSARC bridge;
- synthetic/original/public-domain/licensed fixtures only;
- GUI tests focused on state transitions and workflow correctness rather than pixel-perfect rendering;
- Windows build artifact on meaningful desktop PRs;
- periodic hands-on testing of the packaged `.exe` with a real local project.

## Success criteria

The project succeeds when a normal Windows user can:

1. install/launch the application;
2. provide a song and complete score;
3. confirm the few decisions automation should not make;
4. review and correct the generated Bass, Lead, and Rhythm arrangements inside the application;
5. produce a valid Rocksmith CDLC package with minimal external-tool friction;
6. understand every blocking warning without reading source code or JSON;
7. spend materially less time authoring a song than with a manual workflow.
