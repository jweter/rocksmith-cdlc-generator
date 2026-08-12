# ADR-060: Record First Playable Hardware Evidence and Surface Capture Clipping

## Status

Accepted

## Context

The first real-hardware run of the experimental live tone harness succeeded on the reference Windows laptop and Scarlett 2i2 3rd Gen. The operator heard the processed guitar signal for the `clean`, `crunch`, and `drive` presets.

Four consecutive PortAudio-ASIO runs reported 15.17 ms, 17.83 ms, 18.50 ms, and 19.17 ms round-trip latency, with callback sizes 144, 160, 176, and 192 frames respectively. Every run reported a peak input level of 1.0000.

The successful listening result proves the first playable end-to-end path. The callback drift reinforces the existing PortAudio-ASIO safety concern, while 1.0000 input peaks show that operator-facing clipping feedback is required before tone quality is judged.

## Decision

1. Record the first playable hardware validation in the operator documentation.
2. Treat peak input magnitude at or above 0.99 as clipping-risk evidence and 0.90-0.99 as hot input.
3. Print an explicit input-level status and corrective warning from the experimental live tone command.
4. Do not automatically alter Scarlett gain, buffer, Rocksmith state, tone approval state, or any vendor control-panel setting.
5. Keep PortAudio-ASIO experimental and ineligible for the production Live Tone Test backend until vendor-state preservation and reconnect recovery are proven.

## Consequences

The project now has a measured, reproducible first-playable milestone rather than only synthetic or I/O qualification evidence. Operators are less likely to evaluate DSP presets using already-clipped capture audio. The successful hardware result does not weaken the production backend safety gate.
