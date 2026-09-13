# Arrangement Preview v1

Arrangement Preview v1 is the first read-only multi-arrangement inspection surface inside Song Workspace.

## Purpose

After one complete score has been registered, its Bass, Lead, and Rhythm mappings human-confirmed, the authoritative score fan-out generated, and one shared score-to-recording timeline explicitly promoted, the Windows application can display all available arrangement events on the recording-audio clock used by playback.

The preview supports both current Guitar Pro fan-out (`gp3`, `gp4`, `gp5`) and MusicXML/MXL fan-out because it consumes the generic `ScoreFanoutManifest` and normalized `ImportedSource` outputs rather than a format-specific UI contract.

Score events remain immutable in their imported symbolic clock. Arrangement Preview maps their start/end times through the current promoted shared alignment only for display and navigation. This keeps waveform, playback, playhead, review navigation, and the virtual fretboard synchronized even when the recording has a nonzero offset or tempo drift relative to the score.

## What the user can inspect

- Bass, Lead, and Rhythm event lanes over the current playback/timing viewport;
- event durations and current playhead position on the recording clock;
- string/fret positions when the importer supplied them;
- unresolved physical positions without inventing replacements;
- tuning-aware virtual fretboard views for each arrangement;
- currently sounding or immediately upcoming fretboard positions;
- a deterministic chronological queue of events that still require human review;
- confidence, trust class, techniques, and stable source event indices for review items;
- direct next/previous navigation that seeks synchronized playback to the affected recording position.

## Authority and safety rules

Arrangement Preview is read-only.

Opening the tab, navigating to an event, hearing it, or seeing a position on the fretboard does **not**:

- confirm a Bass/Lead/Rhythm score mapping;
- accept source rights/provenance;
- approve timing;
- accept string/fret placement;
- clear a review-required flag;
- accept techniques or chord fingering;
- mark validation as passed;
- make an arrangement export/package-ready.

The loader refuses to render a mixed or stale arrangement set. It requires:

1. the fan-out manifest to match the currently registered immutable score SHA and format;
2. every displayed arrangement to still have a human-confirmed role/track mapping;
3. every fan-out output to match the registered score provenance and manifest track selection;
4. all displayed arrangements to share one canonical imported score timebase;
5. a current human-promoted shared score-to-recording timeline whose recording, score, authority mapping, and fan-out provenance are still valid;
6. every referenced file to remain inside the project directory.

If shared timing is absent or stale, synchronized arrangement preview fails closed rather than displaying score-clock events against recording-clock playback.

## Performance behavior

The full multi-arrangement canvases redraw while playback is advancing and on explicit navigation/view changes such as seek, stop, zoom, pan, resize, or review navigation. A paused workspace does not continuously recreate the entire score at the playback polling rate.

## Playback clock diagnostics

Arrangement Preview and the shared Timeline both redraw from `ProjectAudioTransport.position_seconds`, polled every 50-80ms while playing (`_poll_playback`). Issue #561 already documented one perceived-lag risk in this path (visuals trailing audible sound before `latency="low"` was requested). `arrangement_preview_clock_diagnostics.analyze_playback_clock_samples()` adds a deterministic, hardware-free detector over a sequence of `(wall_clock_seconds, position_seconds)` poll samples: it flags the reported position jumping backward, stalling while wall-clock time keeps advancing, or drifting away from real-time speed by more than a configurable tolerance, without requiring live audio, Windows, or a running UI. `PlaybackSongWorkspaceWindow._poll_playback` (`song_workspace_playback_ui.py`) now feeds it live: each poll while playing is compared against the previous poll's sample, and a real anomaly persists one `desktop_diagnostics.jsonl` entry per distinct anomaly episode (deduplicated by anomaly code while it stays active; a return to normal playback, or pausing/stopping, re-arms detection for the next episode) via `persist_project_diagnostic()`.

## Next step

The next arrangement-review milestone can build provenance-aware edits on top of these stable event pointers: select an event, create a separate reviewed-chart artifact, correct physical placement/timing/techniques, validate the edit, and explicitly accept it. Raw imported score artifacts must remain immutable evidence.
