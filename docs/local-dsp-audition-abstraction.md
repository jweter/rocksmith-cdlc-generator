# Local DSP Audition Abstraction

## Purpose

Provide a stable data and processing contract between reviewed tone settings, the future Live Tone Test GUI, and whichever local DSP runtime proves reliable on Windows.

## Design goals

- Keep the GUI independent of Pedalboard, VST3, or any specific DSP engine.
- Keep Rocksmith-derived normalized tone metadata separate from local approximation details.
- Label mappings as `exact`, `approximate`, or `unsupported`.
- Fail closed when an unsupported mapping is accidentally enabled.
- Support original/proposed/manual A/B candidates without mutating source data.
- Make the control plane testable in CI without audio hardware.

## Chain model

Each audition candidate is represented by an `AuditionChain` with:

- display name;
- variant (`original`, `proposed`, or `manual`);
- sample rate;
- ordered effect specifications;
- whole-chain bypass state.

Each effect specification can carry:

- generic local effect type;
- reviewer-facing label;
- local parameters;
- source Rocksmith device key when applicable;
- mapping confidence;
- unsupported parameter names;
- bypass state.

## Runtime boundary

Realtime engines implement the `AuditionProcessor` contract. The initial pure-Python processor exists only to prove deterministic behavior and validation in CI. It is not intended to sound like Rocksmith or serve as the final guitar/bass processor.

Potential later production adapters:

- Pedalboard/open DSP effects;
- a VST3 host adapter;
- another Windows-native backend if Scarlett qualification shows materially better latency/stability.

## Human-review boundary

Audition chains are listening aids only. Processing or A/B selection cannot approve a tone, change the staged authoring artifact, or enable injection. If a reviewer changes a staged authoring setting, the existing staged-diff and audition acknowledgement digests must be regenerated.

## Next measurement

The remaining physical measurement is the reference Scarlett 2i2 qualification on the target Windows laptop. Once actual full-duplex stability and latency are known, select the production realtime path and connect it to this abstraction.
