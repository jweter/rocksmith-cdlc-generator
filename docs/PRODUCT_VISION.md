# Product Vision

## What this product should become

Rocksmith CDLC Generator should be a polished Windows desktop authoring application that lets a normal user turn a local song recording and a complete structured score into high-quality Rocksmith 2014 Bass, Lead, and Rhythm CDLC with minimal manual work.

The application should feel like one integrated song-authoring workspace, not a collection of scripts.

The normal user should not need to understand Python, JSON, PowerShell, internal artifact names, provenance manifests, or the order of CLI commands. Those details remain inside the engine and diagnostics layer.

## Core promise

For the strongest path:

> **One recording + one complete score → one shared timing model → Bass + Lead + Rhythm drafts → focused human review → Rocksmith package.**

The software should automate deterministic work aggressively while making the few decisions that truly need a human clear, fast, and pleasant.

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

### Human review should be focused

The product should not make users inspect everything equally. Confidence, provenance, validation, and source disagreement should direct attention toward the places most likely to need correction.

### Explain what to do next

Every blocked state should answer:

1. What is wrong or missing?
2. Why does it matter?
3. What should I do next?
4. Can the application take me directly there?

### Preserve trust

Automatic confidence is evidence, not authority. The app must remain explicit about uncertain mappings, timing, source rights, fingering, tones, and package readiness.

### Local first

Commercial/user media stays local. The application must not rip streaming services or silently upload songs, charts, or packages.

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
8. The app highlights only suspicious timing, notes, chords, techniques, and fingering.
9. Click a problem to hear it, see it on the waveform, and see it on the fretboard.
10. Correct it directly in the workspace.
11. Review metadata, cover art, sections, tones, and package status.
12. Press Build.
13. DLC Builder produces the package through the controlled handoff.
14. The app verifies the returned PSARC and clearly says whether it is ready for manual installation.

## Useful features are encouraged

The GUI should become feature-rich where features materially improve authoring speed, clarity, confidence, or enjoyment. Examples include:

- project dashboard and search;
- drag/drop intake;
- waveform playback;
- loop and slow playback;
- variable-tempo metronome;
- multi-arrangement overlays;
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
- an automatic installer into Rocksmith;
- a system that pretends uncertain generated music is definitely correct;
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
- user confidence in why a project is blocked or ready.

The finished application should make authoring a high-quality three-arrangement CDLC dramatically easier than assembling the same result manually across disconnected tools.
