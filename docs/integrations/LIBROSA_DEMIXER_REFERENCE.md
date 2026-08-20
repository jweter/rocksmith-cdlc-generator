# librosa + demixer Reference Plan

## Purpose
Use mature DSP primitives from `librosa` and architectural lessons from `revelri/demixer` to reduce custom audio-analysis code and improve separation between deterministic signal processing and probabilistic model output.

## librosa posture
Potential direct dependency, subject to license/version review and repository preflight.

Candidate uses:
- onset envelopes;
- tempo/beat candidates;
- chroma/CQT features;
- spectral features;
- resampling/timebase utilities;
- alignment diagnostics.

Any direct adoption must be wrapped in Rocksmith-owned service functions so low-level library choices do not leak through the application.

## demixer posture
Reference architecture only unless a later evaluation justifies a component-level adapter.

Study its end-to-end decomposition:
```text
audio
 -> stem separation
 -> transcription/MIDI
 -> tempo/key/chords
 -> structured outputs
```

The Rocksmith project should not become a clone of demixer. Instead, use the decomposition to validate modular boundaries between:
- source preparation;
- stem generation;
- deterministic DSP;
- transcription evidence;
- score comparison;
- review;
- export.

## Deterministic-versus-probabilistic rule
Whenever possible, deterministic DSP outputs should be stored separately from model-derived outputs. For example, a spectral/onset feature derived by pinned parameters must not be conflated with an AI transcription confidence score.

## Caching/provenance
Every derived analysis artifact should be keyed by:
- input hash;
- analysis type;
- library/model version;
- parameters;
- timebase identity.

## Acceptance criteria
- Fewer bespoke DSP implementations where a mature library is demonstrably equivalent or better.
- Clear module boundaries prevent dependency-specific data structures from becoming canonical.
- Architecture supports independent replacement of stem, DSP, and transcription providers.
- Regression tests cover important deterministic transforms.

## Non-goals
- importing demixer wholesale;
- replacing human review;
- generating final arrangements directly from DSP/transcription output.

## Rollback
Keep all library-specific calls behind adapters/services. If a dependency becomes unsuitable, reimplement or substitute that boundary without changing canonical project state.