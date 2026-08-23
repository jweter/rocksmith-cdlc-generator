# Product Vision

## What this product should become

Rocksmith CDLC Generator should be a polished Windows desktop authoring application that lets a normal user turn a local song recording and a complete structured score into high-quality Rocksmith 2014 Bass, Lead, and Rhythm CDLC with minimal manual work.

The application should feel like one integrated song-authoring workspace, not a collection of scripts.

The normal user should not need to understand Python, JSON, PowerShell, internal artifact names, provenance manifests, or the order of CLI commands. Those details remain inside the engine and diagnostics layer.

## Core promise

For the strongest path:

> **One recording + one complete score → one shared timing model → Bass + Lead + Rhythm drafts → focused human review → Rocksmith package.**

The mature product should also support multiple independent score/tab/reference candidates when they are available. Additional sources are evidence, not automatic authority: the app should be able to compare them against the recording, rank them globally and by section, surface disagreement, and derive a provenance-preserving consensus draft for focused review.

The software should automate deterministic work aggressively while making the few decisions that truly need a human clear, fast, and pleasant.

## Current execution focus

The first packaged Windows desktop application and Song Workspace v1 are complete. The active product milestone is now **interactive playback + waveform navigation** inside Song Workspace:

- render a cached waveform from the deterministic normalized project audio;
- play/pause/stop local audio from the packaged Windows application;
- keep the moving playhead on the same time axis as beats, shared-timeline anchors, and review findings;
- click-to-seek;
- zoom and pan the timeline without losing synchronization;
- use this surface as the foundation for loop/slow review, metronome playback, timing-anchor correction, and arrangement event editing.

This progression is deliberate: Song Workspace should become useful for real authoring as early as possible instead of waiting for every backend feature to be perfect.

## Product principles

### Desktop first

The Windows application is the product. The CLI and Python library exist to make the engine testable, reproducible, scriptable, and debuggable.

### One song workspace

Every important task should converge on a persistent Song Workspace:

- project/source status;
- waveform and playback;
- timing and beat review;
- Bass, Lead, and Rhythm arrangement tabs;
- fretboard and note/chord editing;
- review queue;
- validation;
- metadata and tones;
- export/package status.

Users should not have to mentally reconstruct project state from separate utilities.

### Align once, reuse everywhere

A complete score is a project-level source. Bass, Lead, and Rhythm are arrangement projections of that source. When the score is aligned to the recording, all confirmed arrangements should inherit the same reviewed song timing.

### Multiple sources should become evidence, not chaos

When multiple Guitar Pro files, MusicXML scores, tabs, chord sheets, transcription candidates, or human reference observations are available, the product should preserve them as independent evidence identities instead of forcing the user to choose one blindly.

Future source reconciliation should:

- compare candidates against the recording and against one another;
- rank candidates globally and by song section/phrase;
- expose why one source ranked higher;
- highlight disagreement regions directly in the review workflow;
- allow the strongest source to vary by section;
- derive a consensus draft only with event-level provenance and confidence;
- keep ambiguous disagreements explicitly review-required.

The detailed future design is recorded in `docs/multi-source-score-reconciliation.md`.

### Human reference material can resolve uncertainty

A user may own professionally published guitar/bass score books or other lawful reference material and use them privately to verify disputed sections. The application should support recording structured human-verification decisions without requiring copyrighted score pages to become repository content.

A private photograph or scan of a limited page/section may be used as review evidence in a local/private workflow. The page image itself should remain outside the repository and distribution artifacts; only the resulting verification decision, provenance metadata, and non-infringing derived observations should be persisted where appropriate.

### Human review should be focused

The product should not make users inspect everything equally. Confidence, provenance, validation, and source disagreement should direct attention toward the places most likely to need correction.

### Explain what to do next

Every blocked state should answer:

1. What is wrong or missing?
2. Why does it matter?
3. What should I do next?
4. Can the application take me directly there?

### Preserve trust

Automatic confidence is evidence, not authority. The app must remain explicit about uncertain mappings, timing, source rights, fingering, tones, source disagreement, and package readiness.

### Local first

Commercial/user media stays local. The application must not rip streaming services or silently upload songs, charts, score-book images, or packages.

### Never touch the live game automatically

Generation, validation, staging, and package verification remain outside the live Rocksmith installation. Installation remains a deliberate user action.

## Ideal user experience

A mature version should look roughly like this:

1. Open the app.
2. Drag in a song recording and score.
3. The app identifies tracks and proposes Bass/Lead/Rhythm mappings.
4. Confirm the mappings.
5. The app analyzes the recording and aligns the score.
6. Review one timing screen and accept/correct it.
7. Bass, Lead, and Rhythm drafts appear automatically.
8. The app highlights only suspicious timing, notes, chords, techniques, fingering, and source disagreements.
9. Click a problem to hear it, see it on the waveform, and see it on the fretboard.
10. Correct it directly in the workspace; where useful, compare alternate score/tab candidates or record a human verification from lawful private reference material.
11. Review metadata, cover art, sections, tones, and package status.
12. Press Build.
13. DLC Builder produces the package through the controlled handoff.
14. The app verifies the returned PSARC and clearly says whether it is ready for manual installation.

For projects with multiple candidate sources, a later mature workflow should add a Compare Sources surface that ranks candidates overall and by section, navigates directly to disagreement regions, and can propose a provenance-preserving consensus arrangement for review.

## Useful features are encouraged

The GUI should become feature-rich where features materially improve authoring speed, clarity, confidence, or enjoyment. Examples include:

- project dashboard and search;
- drag/drop intake;
- waveform playback;
- loop and slow playback;
- variable-tempo metronome;
- multi-arrangement overlays;
- multi-source candidate comparison and ranking;
- section/phrase-level source winners;
- disagreement-region navigation;
- provenance-preserving consensus drafts;
- private human-reference verification records;
- virtual fretboard;
- chord/fingering editor;
- keyboard shortcuts;
- undo/redo for editing;
- review queue navigation;
- confidence heatmaps;
- section/phrase markers;
- tone audition;
- tool diagnostics;
- autosave/recovery;
- project health summary;
- export readiness dashboard;
- high-DPI and accessibility support.

Nice-to-have features are welcome when they strengthen the desktop product. They should not displace completion of the core end-to-end Windows workflow.

## What the product is not

It is not:

- a streaming downloader;
- a piracy tool;
- a repository/distribution mechanism for commercial score books or private score-page images;
- an automatic installer into Rocksmith;
- a system that pretends uncertain generated music is definitely correct;
- a system that assumes one tab/score candidate is authoritative merely because it was loaded first;
- a Bass-only tool;
- a CLI-first developer utility as its final form.

## North-star success metric

The most important metric is **human editing minutes per finished song minute**.

Supporting metrics include:

- percentage of songs reaching package-ready state;
- number of user interventions required;
- time spent locating versus fixing problems;
- validation defects caught before game testing;
- package build success rate;
- application crashes/recovery success;
- user confidence in why a project is blocked or ready;
- for multi-source projects, number of disagreement regions resolved automatically versus requiring human review and whether reconciliation measurably reduces correction time.

The finished application should make authoring a high-quality three-arrangement CDLC dramatically easier than assembling the same result manually across disconnected tools.
