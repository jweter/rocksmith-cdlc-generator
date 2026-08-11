# ADR-053: Backend-neutral local DSP audition abstraction

## Status

Accepted

## Context

The Scarlett 2i2 audio-I/O proof establishes how a future Live Tone Test can acquire and monitor instrument audio, but the product should not couple tone-review data or GUI controls directly to one DSP library. Realtime backend choice may change after hardware qualification.

The application also needs to distinguish exact, approximate, and unsupported mappings when translating Rocksmith tone metadata into legal local audition effects.

## Decision

Introduce a backend-neutral audition DSP model consisting of:

- `AuditionChain` for one original/proposed/manual candidate;
- ordered `AuditionEffectSpec` entries with parameters, source Rocksmith device identity, mapping confidence, unsupported-parameter notes, and bypass state;
- an `AuditionProcessor` protocol implemented by realtime backends later;
- deterministic validation that rejects non-finite parameters and requires unsupported mappings to remain bypassed;
- A/B selection that returns an isolated copy and requires a common sample rate; and
- a deliberately small pure-Python reference processor for CI and contract tests.

The reference processor is not a production amp/effect emulator and must not be represented as equivalent to Rocksmith DSP. Production adapters such as Pedalboard or VST3 hosts can implement the same processor contract later.

## Consequences

The GUI and review workflow can be designed against stable audition-chain data without depending on the final Windows DSP runtime. Mapping uncertainty remains visible and unsupported effects fail closed instead of being silently approximated.

This slice performs no audio-device access, records no audio, does not modify the live Rocksmith installation, and does not approve tone settings.

## Follow-up

After private Scarlett qualification results are available, select/tune the realtime audio backend and add a production DSP adapter. Then add the Rocksmith-device-to-audition mapping layer with explicit confidence and unsupported-parameter reporting.
