# Rocksmith CDLC Generator — Canonical Roadmap

This file is the canonical implementation roadmap. The product goal is a real Windows desktop application that turns one local song recording plus one complete structured score, when available, into reviewed Rocksmith 2014 Bass, Lead, and Rhythm arrangements with as little manual authoring as practical.

The GUI is the primary product. The CLI remains the deterministic engine/debugging surface.

## North-star workflow

```text
Launch Windows app
  → choose local recording + complete score
  → review rights/provenance
  → confirm Bass / Lead / Rhythm mappings
  → analyze recording + fan out score tracks
  → align once
  → review/correct one shared timing model
  → generate three arrangement drafts
  → review notes/chords/fingering/techniques
  → validate
  → metadata / cover / tones
  → Rocksmith XML + DLC Builder handoff
  → build + verify PSARC
  → manual installation
```

## Governing rules

1. Build the Windows product continuously. Defects are recorded as GitHub Issues and do not hijack the roadmap unless they block the normal desktop path, cause reproducible wrong output/data loss, or violate a hard safety boundary.
2. Source media and registered score bytes are immutable identities.
3. One complete score is a project-level musical source, not three independent imports.
4. Bass, Lead, and Rhythm inherit one reviewed score-to-recording timing model whenever the shared-score workflow is used.
5. Human confirmation remains required for uncertain rights/provenance, source mappings, timing acceptance, fingering/playability, tone acceptance, and package readiness.
6. Never invent unresolved guitar string/fret positions or silently turn confidence into authority.
7. Never download/rip streaming-reference media.
8. Never modify the live Rocksmith installation or NoCableLauncher.
9. Never commit commercial audio, private packages, CFSM exports, Ubisoft-derived content, or generated private project data.
10. Packaging remains validation-gated.

## Completed product foundation

Already implemented and reusable:

- immutable local project/audio ingest and FFmpeg normalization;
- beat/tempo analysis and Bass transcription/mapping;
- Guitar Pro 3–5 and MusicXML complete-score intake;
- explicit Bass/Lead/Rhythm track confirmation;
- score fan-out and one shared score-to-recording timeline;
- Lead/Rhythm drafts inheriting shared timing;
- validation/review artifacts and Rocksmith XML authoring;
- DLC Builder staging and PSARC registration/verification;
- packaged Windows desktop executable built in GitHub Actions;
- Song Workspace with project health, arrangement state, review queue, provenance summary, and synchronized timeline;
- cached waveform, local play/pause/stop, moving playhead, click-to-seek, zoom/pan, and Windows audio runtime.

## Current milestone — Reviewed timing editor

This is the active milestone.

The Song Workspace is becoming a real correction surface rather than only a viewer.

### Required scope

- loop-range selection directly from the shared timeline;
- 50%, 75%, and 100% review playback while keeping chart/timeline coordinates in source-song time;
- variable-tempo click derived from the actual beat schedule;
- select the nearest analyzed beat from the timeline cursor;
- nudge reviewed beat timing by ±1 ms and ±10 ms;
- enter exact timestamps;
- lock/unlock trusted anchors;
- deterministic interpolation/refit between surrounding locked anchors;
- preserve raw detector timing unchanged;
- save reviewed timing as a separate recording/tempo-map-bound artifact;
- explicitly promote reviewed timing only by a human action;
- surface reviewed/locked timing visually in Song Workspace;
- keep the packaged Windows playback path stable while these controls are added.

### Included reliability work because it affects normal desktop use

- close/stop the PortAudio stream outside the callback lock so closing Song Workspace after playback cannot deadlock the Tk UI.

Other playback findings remain tracked as Issues and do not stop this milestone.

## Next milestone — Arrangement review and editing

Make Bass, Lead, and Rhythm directly reviewable/editable in Song Workspace:

- note/chord event overlays on the waveform/timeline;
- current/upcoming-note visualization;
- direct navigation from review findings to affected events;
- note timing correction;
- string/fret correction;
- chord/fingering editor;
- tuning visibility/editor where supported;
- technique review;
- virtual Bass/guitar fretboard;
- confidence/provenance display;
- source-disagreement visualization;
- undo/redo for manual arrangement edits.

No unresolved/unverified physical guitar position may pass silently into export.

## Following milestone — Complete desktop build flow

Bring the remaining end-to-end engine workflow into the GUI:

- three-arrangement validation dashboard;
- metadata and cover art;
- tones and tone regions;
- Rocksmith XML export;
- DLC Builder discovery/project preparation/launch;
- package staging and readiness view;
- returned PSARC registration and integrity verification;
- tool and audio-device diagnostics.

Normal use should not require PowerShell.

## Following milestone — Installable release

- stable versioning;
- branded icon/application metadata;
- GitHub release artifacts;
- installer or equivalently simple Windows distribution;
- first-launch dependency/tool diagnostics;
- user-settings/project migration and recovery behavior;
- optional safe update notification.

## Later capability expansion

Important, but not allowed to displace completion of the desktop workflow:

- stronger audio-only transcription for songs without structured scores;
- additional score formats through safe adapters;
- richer technique detection;
- dynamic difficulty controls;
- section/phrase inference;
- tone-region detection and Rocksmith device mapping;
- improved source reconciliation;
- batch/project-library tools;
- benchmark suite for real correction-time measurement;
- optional local AI assistance only where it measurably reduces editing time without weakening provenance or human gates.

## Issue policy

When development or Codex review finds an error:

- create/update a GitHub Issue with reproduction context and expected fix direction;
- continue the active product milestone by default;
- interrupt only for normal-path blockers, reproducible wrong output/data loss, or hard safety violations;
- fix accumulated backlog deliberately in later reliability/hardening passes.

## Success criteria

The project succeeds when a normal Windows user can launch the app, provide a song and score, make the few decisions automation should not make, review/correct Bass + Lead + Rhythm inside the application, and produce a valid Rocksmith CDLC package with materially less authoring effort than a manual workflow.
