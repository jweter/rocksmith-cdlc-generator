# ADR-052 — Scarlett 2i2 Audio I/O Proof Before GUI Integration

## Status

Proposed

## Context

The planned Live Tone Test depends on reliable low-latency Windows audio I/O through the user's Focusrite Scarlett 2i2. Deferring hardware validation until the full GUI is built would allow a critical device/driver assumption to become a late architectural blocker.

The application must also remain independent of Rocksmith's proprietary Real Tone Cable requirement and must not couple the GUI directly to one Python audio library.

## Decision

Build a standalone Scarlett 2i2 hardware-proof layer immediately after the tone listening/approval contracts stabilize and before full GUI realtime-audio integration.

The proof introduces:

- a small backend-neutral `AudioBackend` contract;
- endpoint and qualification data models;
- physical Scarlett/Focusrite endpoint resolution that excludes loopback endpoints;
- Input 1/2 and stereo-output validation;
- a short explicit full-duplex monitor probe;
- separate functional-I/O and low-latency readiness results;
- re-enumeration rather than persisted numeric device IDs for reconnect recovery;
- an optional `python-sounddevice`/PortAudio adapter as the first implementation;
- mocked/synthetic CI tests with no hardware requirement.

The operator must explicitly pass `--run` before a stream is opened. The probe does not record audio to disk.

## Why python-sounddevice first

Its current public API provides Windows endpoint enumeration, host API information, setting validation, full-duplex callback/raw streams, and actual stream latency reporting. Current pip-installed Windows builds can optionally load an ASIO-capable PortAudio DLL when enabled before import.

This remains an adapter choice, not a permanent dependency boundary. If reference-machine testing shows unacceptable latency or device-loss behavior, another backend can replace it behind `AudioBackend`.

## Consequences

### Positive

- de-risks Scarlett compatibility before GUI investment;
- removes any Real Tone Cable dependency from the application architecture;
- gives a measurable latency/callback baseline;
- makes reconnect behavior deterministic through re-enumeration;
- keeps CI hardware-independent;
- preserves the option to replace the realtime backend later.

### Tradeoffs

- CI cannot prove actual hardware behavior;
- reported stream latency is a useful driver/backend metric but not a complete acoustic round-trip measurement;
- ASIO behavior must be qualified privately on the reference Windows machine;
- the proof provides dry monitoring only; DSP audition comes later.

## Safety

This decision does not modify the live Rocksmith installation, inspect commercial DLC/audio, redistribute Ubisoft-derived content, or record instrument audio to persistent storage. Private hardware qualification results remain ignored/generated data.

## Next

Run the proof on the reference Scarlett 2i2 machine. Measure normal and ASIO-capable paths across practical buffer sizes. Use those results to choose the backend configuration for the later Live Tone Test DSP and GUI integration.
