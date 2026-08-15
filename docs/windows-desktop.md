# Windows desktop application

The desktop application is the primary product direction for the Rocksmith CDLC Generator. The CLI remains useful for automation, testing, and advanced troubleshooting, but normal users should not need PowerShell to create a song project.

## Product flow

The intended desktop workflow is:

1. Select one local song recording.
2. Select one complete Guitar Pro or MusicXML score when available.
3. Create a project with Bass, Lead, and Rhythm enabled.
4. Review local-source rights/provenance.
5. Review and explicitly confirm score track mappings for Bass, Lead, and Rhythm.
6. Run safe deterministic analysis and drafting steps.
7. Review the one shared score-to-recording timeline and promote it once for all arrangements.
8. Review Bass, Lead, and Rhythm drafts, validation flags, fingering, timing, and source disagreements.
9. Export Rocksmith 2014 arrangement XML.
10. Prepare and stage DLC Builder inputs outside the live Rocksmith installation.
11. Register a user-built PSARC for manual installation only after readiness checks pass.

Human gates remain visible. The desktop app must not silently accept uncertain mappings, source rights, timing, fingering, tone choices, or package readiness.

## Desktop v1

The first desktop milestone provides a real Windows workspace backed by the existing project engine:

- create a three-arrangement project from local audio;
- optionally register the complete score during project creation;
- open and remember recent projects;
- inspect the live workflow plan and next required action;
- inspect score tracks and explicitly confirm Bass/Lead/Rhythm mappings;
- record local-source rights/provenance reviews;
- run the bounded automatic workflow without invoking a shell;
- keep long-running work off the GUI thread;
- retain an activity log and surface actionable errors;
- build a Windows application bundle with `RocksmithCDLCGenerator.exe` in GitHub Actions.

## Planned workspace expansion

The desktop workspace should grow into a full authoring application rather than a collection of command buttons. High-value additions include:

- recent-project dashboard, project search, favorites, and project health badges;
- drag-and-drop audio, score, cover art, DLC Builder project, and PSARC intake;
- source inspector showing hashes, rights state, format, duration, track inventory, and provenance;
- visual score-mapping table with importer confidence, tuning, note counts, and side-by-side track preview;
- shared-timeline review with beat-grid visualization, anchor editing, offset controls, confidence diagnostics, and A/B playback;
- arrangement tabs for Bass, Lead, and Rhythm;
- waveform + beat grid + note overlay;
- Rocksmith-style fretboard preview and playhead;
- loop selection and slowed playback for difficult review regions;
- validation queue with next/previous issue navigation and one-click acknowledgement/fix workflows;
- explicit unresolved string/fret highlighting and hard export blocking;
- chord/fingering editor for Lead and Rhythm;
- tuning editor and capo support where Rocksmith constraints permit it;
- tone-reference research and audition workspace with explicit human acceptance;
- metadata editor for artist/title/album/year/cover/DLC key;
- export dashboard showing exactly which arrangements are ready and why others are blocked;
- DLC Builder executable discovery, project preparation, launch, and return-to-app status;
- PSARC staging/verification without modifying the live Rocksmith installation;
- persistent application settings and tool-path detection;
- FFmpeg, DLC Builder, bridge, audio-device, and dependency diagnostics;
- cancellable background jobs and progress reporting;
- crash/error report export that excludes private media by default;
- keyboard shortcuts, accessible labels, scalable UI, and high-DPI Windows support;
- optional theme choices after core usability is stable;
- automatic update/release discovery only if it can be done without weakening local-first safety.

## Safety boundaries

The desktop application must preserve the same boundaries as the core engine:

- never download or rip streaming-reference media;
- never modify the live Rocksmith installation or NoCableLauncher;
- never infer redistribution rights from local possession;
- never auto-confirm musical/source decisions merely because confidence is high;
- never invent unresolved guitar string/fret positions;
- never package an arrangement that fails the applicable validation/review gates;
- keep generated/private media and user package data out of Git.
