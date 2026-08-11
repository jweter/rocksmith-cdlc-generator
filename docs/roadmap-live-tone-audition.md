# Roadmap Placement — Live Instrument Tone Audition

This roadmap note supplements `PROJECT_PLAN.md` and `docs/song-preview-timing-editor.md` so the live instrument audition feature remains explicitly scheduled while the canonical roadmap evolves.

## Placement

### Milestone 10.5 — Tone research and Rocksmith tone reconstruction
Prerequisite engine work:

- normalized local Rocksmith tone references;
- human-reviewed tone proposals and staged settings;
- explicit staged-vs-original settings diff;
- final review provenance;
- human listening/audition acknowledgement contracts;
- guarded final approval that can require a current positive audition;
- a mapping from Rocksmith device identities/settings to a legal local audition approximation.

Realtime DSP is **not** required to finish the tone-research engine milestone, but the human-review and provenance contracts created here must be ready for later audition.

### Early hardware de-risking slice — Scarlett 2i2 Audio I/O Proof

Do this **immediately after the audition-gated approval contracts are stable, before the full Song Workspace GUI depends on realtime audio**.

Reference hardware: Focusrite Scarlett 2i2 on Windows 11 using the installed Focusrite driver stack. The proof should remain backend-focused and should not require the final GUI.

Validate:

- enumerate Windows audio endpoints and identify the Scarlett cleanly;
- open Scarlett Input 1 and Input 2 independently as mono instrument inputs;
- avoid loopback channels when present;
- route monitored stereo output to Scarlett Outputs 1/2/headphones;
- prove bypassed low-latency monitoring;
- meter input level and clipping;
- report sample rate, buffer size, and practical round-trip/monitoring latency where measurable;
- exercise common sample-rate/buffer configurations;
- fail clearly on unsupported configuration;
- recover or report cleanly after device disconnect/reconnect;
- keep the audio-I/O backend behind an abstraction so a better ASIO-capable implementation can replace an initial prototype without rewriting GUI/tone logic.

CI remains synthetic/mock-based. Actual Scarlett qualification is a manual/private hardware test and must not record or commit user audio.

**Exit criterion:** the project has evidence that the Scarlett 2i2 can serve as the normal guitar/bass interface for the future Live Tone Test without a Rocksmith Real Tone Cable. If the first backend cannot meet practical latency/reliability needs, change the backend here rather than after GUI integration.

### Milestone 11 — Song Preview & Timing Editor
The GUI begins here. Live Tone Audition is scheduled as a later Milestone 11 Song Workspace capability after basic playback/timing/chart review is functional, consuming the already-proven Scarlett/audio-I/O abstraction.

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

0. **Before GUI dependency: qualify the Scarlett 2i2/audio-I/O abstraction on Windows 11.**
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
11. **Live Tone Test: proven local interface monitoring + approximate DSP audition.**
12. **Private dry-DI capture + A/B candidate comparison + listening acknowledgement.**
13. Validation/build controls.
14. Packaged Windows executable.

## Dependency rule

Do not delay the initial GUI until all Live Tone Audition DSP features are ready. However, do de-risk Scarlett/audio-I/O access before the GUI becomes dependent on realtime monitoring. The Song Workspace can then start as soon as timing artifacts are stable, while tone DSP mapping evolves behind a proven audio interface abstraction.

## Safety boundary

- no writes to the live Rocksmith installation;
- no Ubisoft DSP extraction or redistribution;
- no committed commercial audio/DLC or private DI recordings;
- approximate audition mappings must be labeled as approximate;
- listening does not itself approve or inject a tone;
- final musical/tone authority remains human.

See `docs/live-tone-audition.md` for the detailed feature specification.
