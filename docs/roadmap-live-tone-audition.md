# Roadmap Placement — Live Instrument Tone Audition

This roadmap note supplements `PROJECT_PLAN.md` and `docs/song-preview-timing-editor.md` so the live instrument audition feature remains explicitly scheduled while the canonical roadmap evolves.

## Placement

### Milestone 10.5 — Tone research and Rocksmith tone reconstruction
Prerequisite engine work:

- normalized local Rocksmith tone references;
- human-reviewed tone proposals and staged settings;
- explicit staged-vs-original settings diff;
- final review provenance;
- a mapping from Rocksmith device identities/settings to a legal local audition approximation.

Realtime audio is **not** required to finish the tone-research engine milestone, but the data contracts created here should be designed for later audition.

### Milestone 11 — Song Preview & Timing Editor
The GUI begins here. Live Tone Audition is scheduled as a later Milestone 11 Song Workspace capability after basic playback/timing/chart review is functional.

Add to the Milestone 11 scope:

- **Live Tone Test panel** for guitar and bass through a local audio interface;
- low-latency monitored input/output;
- approximate local DSP preview of proposed tone chains;
- tone-region selection from the timeline;
- original/proposed/manual A/B comparison;
- private dry-DI loop capture and deterministic replay;
- visible mapping-confidence/unsupported-parameter warnings;
- human listening acknowledgement before final tone approval.

### Milestone 12 — Full Windows desktop application
Productionize the audition workflow:

- persistent audio-device preferences;
- robust reconnect/device-loss handling;
- polished latency/buffer controls;
- optional local VST3 hosting if the prototype proves stable and supportable;
- installer/runtime packaging for optional realtime-audio dependencies;
- end-to-end operator workflow with no PowerShell requirement.

## Revised GUI implementation sequence

The intended GUI sequence is now:

1. Stable normalized-audio + beat-map artifacts.
2. Minimal PySide6/Qt Song Workspace shell.
3. Waveform + audio playback + variable-tempo metronome.
4. Beat-grid rendering + manual anchor editing.
5. Looping + timing diagnostics.
6. Bass note overlay/event correction.
7. Virtual fretboard.
8. Lead/Rhythm overlays.
9. Technique/section/phrase review.
10. Tone-region and real Rocksmith component review.
11. **Live Tone Test: local interface monitoring + approximate DSP audition.**
12. **Private dry-DI capture + A/B candidate comparison + listening acknowledgement.**
13. Validation/build controls.
14. Packaged Windows executable.

## Dependency rule

Do not delay the initial GUI until Live Tone Audition is ready. The Song Workspace should start as soon as the timing artifacts are stable enough for real correction work. Live audition depends on the tone-review contracts but can be developed incrementally once the GUI shell and tone-review surfaces exist.

## Safety boundary

- no writes to the live Rocksmith installation;
- no Ubisoft DSP extraction or redistribution;
- no committed commercial audio/DLC or private DI recordings;
- approximate audition mappings must be labeled as approximate;
- listening does not itself approve or inject a tone;
- final musical/tone authority remains human.

See `docs/live-tone-audition.md` for the detailed feature specification.
