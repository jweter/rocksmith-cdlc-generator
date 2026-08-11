# Live Instrument Tone Audition

## Purpose

The desktop Song Workspace should let a human reviewer plug in a guitar or bass through a local audio interface and audition proposed tone/effect settings before packaging or launching Rocksmith.

This is a human-review feature, not an automatic tone-approval system. The purpose is to catch musically wrong gain, EQ, dynamics, modulation, delay, reverb, level, and transition choices earlier in the authoring workflow.

## Product position

Live Tone Audition belongs inside the Song Preview & Timing Editor / Song Workspace rather than as a separate utility. It should consume the same tone evidence, reviewer proposals, staged settings, staged-vs-original diffs, and final human-review provenance already produced by the engine.

The first implementation should be an approximation layer built from legal/open DSP or user-installed local plugins. It must not copy, redistribute, or attempt to extract Ubisoft proprietary DSP implementations.

## Intended signal path

```text
guitar / bass
    ↓
local audio interface input
    ↓
low-latency dry capture
    ↓
audition DSP chain
    ↓
headphones / monitors through the selected local output
```

The live audition path must never write to or modify the Rocksmith installation.

## GUI panel

The Song Workspace should expose a **Live Tone Test** panel with at least:

- instrument mode: Guitar or Bass;
- input device and input channel selection;
- output device selection;
- sample rate, buffer size, and measured/reported latency;
- input level meter and clipping warning;
- monitoring enable/bypass;
- currently selected arrangement and tone region;
- visible effect-chain order;
- visible mapped device/effect parameters;
- A/B switching between original/current, proposed reference, and manually adjusted audition settings;
- explicit Reject, Keep Editing, and Continue to Review actions.

No listening action should silently mark a component or tone approved.

## Audition DSP boundary

The audition engine should translate a Rocksmith tone proposal into a local approximation using permitted DSP components. Initial candidates include a Python-compatible realtime processing layer and/or locally installed VST3 effects.

The translation layer should preserve provenance:

- Rocksmith device key being approximated;
- local audition effect/plugin used;
- parameter mapping;
- mapping confidence;
- parameters that could not be represented;
- whether the mapping is exact, approximate, or unavailable.

Unknown mappings must remain visible rather than being guessed silently.

## Dry-DI comparison loop

Add a private short-loop capture mode so the reviewer can play one riff once and compare the same performance through several candidate tones.

Suggested workflow:

```text
arm private DI capture
    ↓
play 5–15 second riff
    ↓
store dry DI in ignored private workspace
    ↓
replay through Tone A / Tone B / Tone C
    ↓
A/B or blind compare
    ↓
record reviewer preference / continue editing
```

Dry DI recordings are generated private data. They must remain under ignored private storage and must never be committed automatically.

## Tone-region audition

When the song has multiple tone regions, the user should be able to:

- select a region from the timeline;
- audition that region's proposed tone live;
- audition the transition into the next region;
- compare relative loudness and wet/dry balance between adjacent tones;
- flag a transition or tone as needing revision.

Later, dry-DI playback may follow timeline tone-change markers automatically to preview a whole multi-tone sequence outside Rocksmith.

## Human-review integration

Planned review flow:

```text
tone research / local reference evidence
    ↓
reviewer proposal
    ↓
explicit component accept/reject staging
    ↓
staged-vs-original settings diff
    ↓
Live Tone Test / dry-DI A-B audition
    ↓
human listening acknowledgement
    ↓
explicit final component/tone approval
    ↓
validation / packaging gate
```

The listening acknowledgement should eventually bind to the staged tone settings/diff digest so changing settings after listening requires a fresh audition acknowledgement.

## Safety rules

1. Never modify the live Rocksmith installation.
2. Never redistribute Ubisoft-derived DSP, device payloads, commercial DLC, or commercial audio.
3. Use only normalized private metadata for Rocksmith tone references.
4. Keep all dry DI captures and rendered audition audio under ignored private storage.
5. Do not make an approximate local DSP mapping appear exact.
6. Human listening remains required for uncertain musical/tone decisions.
7. Audition success alone does not make a tone injection-ready.
8. Device access must be explicit and local; no background recording.

## Implementation slices

### Slice A — Audio I/O proof
- Enumerate Windows audio input/output devices.
- Open one mono instrument input and stereo monitor output.
- Provide bypassed low-latency monitoring.
- Meter input level and report buffer/latency information.
- Test with synthetic audio in CI; hardware testing remains manual/private.

### Slice B — Local DSP abstraction
- Define a small audition effect-chain interface independent of Rocksmith device definitions.
- Implement a few generic building blocks: gate, gain/drive, EQ/filter, compression, delay, modulation, and reverb.
- Keep the runtime optional so core non-GUI workflows do not require realtime audio dependencies.

### Slice C — Rocksmith-to-audition mapping
- Map known local Rocksmith tone families/device keys to approximate audition chains.
- Store mapping confidence and unsupported parameters.
- Require human review for low-confidence mappings.

### Slice D — GUI Live Tone Test
- Add device selection, transport/monitor controls, chain visualization, parameter controls, bypass, and A/B comparison.
- Integrate selected arrangement/tone-region context from the Song Workspace.

### Slice E — Private dry-DI loop
- Capture a short dry riff to ignored private storage.
- Replay it deterministically through candidate tone chains.
- Support rapid A/B comparison without requiring repeated performances.

### Slice F — Approval provenance
- Record that the human listened to a specific staged settings digest.
- Invalidate the listening acknowledgement when staged settings change.
- Keep final component/tone approval as a separate explicit action.

## Acceptance criteria

The feature is useful when a reviewer can:

- plug in a guitar or bass through a supported local interface;
- hear low-latency monitored audio through the app;
- select a proposed tone from the Song Workspace;
- hear a clearly labeled local approximation of that tone;
- adjust audition parameters without silently changing approved authoring data;
- A/B multiple candidates using the same private dry-DI performance;
- identify and reject obviously wrong tone choices before launching Rocksmith;
- preserve a traceable human listening decision without bypassing final approval.

## Success metric

Reduce the number of package → launch Rocksmith → discover bad tone → rebuild cycles while preserving human authority over subjective tone quality.
