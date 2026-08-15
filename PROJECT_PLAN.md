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
- reviewed timing with loop/slow playback, variable-tempo click, locked anchors, deterministic refit, and explicit promotion;
- Lead/Rhythm drafts inheriting current reviewed shared timing;
- validation/review artifacts and Rocksmith XML authoring;
- DLC Builder staging and PSARC registration/verification;
- packaged Windows desktop executable built in GitHub Actions;
- Song Workspace with project health, arrangement state, review queue, provenance summary, synchronized waveform/timeline, and playback;
- synchronized Bass/Lead/Rhythm score-event preview on the recording clock;
- review-item navigation and tuning-aware virtual fretboard;
- provenance-aware physical string/fret acceptance with Lead/Rhythm draft invalidation;
- direct arbitrary arrangement-event selection with ambiguity-preserving chord-note choice.

## Current milestone — Arrangement event timing editing v1

This is the active small slice of Arrangement event editing v2.

### Required scope

- explicit onset and duration controls for one directly selected Bass/Lead/Rhythm event;
- provenance-aware review artifact separate from imported score/fan-out data;
- bind every accepted timing decision to the current score, fan-out, promoted shared timeline, source track, stable event index, original onset/duration, and MIDI pitch;
- store accepted values on the recording clock used by playback and preview;
- reject negative starts, non-positive durations, and edits extending beyond the recording;
- overlay current reviewed timing in synchronized three-arrangement preview;
- route current reviewed Lead/Rhythm timing into regenerated shared-timeline drafts without mutating source fan-out JSON;
- bind Lead/Rhythm draft provenance to the reviewed-event-timing layer SHA so later edits make old drafts stale;
- preserve existing downstream validation/export/package invalidation on regeneration;
- keep Bass timing review visible in preview while explicitly leaving Bass authoring/export integration for a later deliberate slice;
- deterministic tests for source immutability, recording bounds, preview overlay, draft staleness, and regenerated timing.

Timing acceptance does not accept pitch, techniques, physical position, source rights, mapping, validation, tones, or package readiness.

## Next milestone — Arrangement technique editing

Continue the same reviewed-chart authority model with one small explicit editor at a time:

- technique review/editing for selected events;
- chord/fingering editor;
- undo/redo for accepted manual arrangement edits;
- direct regeneration/invalidation after accepted edits;
- confidence/provenance and source-disagreement visualization;
- integrate reviewed event timing/position overlays into the separate Bass authoring path deliberately rather than implicitly.

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
