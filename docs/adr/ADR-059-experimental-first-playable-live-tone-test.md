# ADR-059: Experimental first-playable live tone test

## Status

Accepted

## Context

The project has proven native Focusrite ASIO full-duplex guitar I/O and usable reported latency on the reference Scarlett 2i2 3rd Gen. The current PortAudio/sounddevice ASIO adapter is not production-safe because opening it can renegotiate the vendor control-panel buffer. ADR-057 therefore made native ASIO stream opening fail closed by default, and ADR-058 requires vendor-state preservation before a backend can power production live audition.

That safety boundary should not prevent a deliberately controlled hardware experiment that proves the user-facing value of realtime local DSP before the final backend is complete.

## Decision

Add a separate experimental live tone test that:

- reuses the existing native Focusrite ASIO path only after explicit acknowledgement that the buffer may change;
- routes one selected instrument input through the existing backend-neutral audition processor and back to stereo output;
- provides only generic local presets built from gain and soft clipping;
- writes no audio to disk;
- never marks a tone approved, injection-safe, or production-ready;
- remains outside the production backend safety gate;
- tells the operator to inspect and restore the Focusrite buffer after the test if necessary.

The backend exposes a processed-monitor callback boundary so the first playable experiment does not couple DSP models directly to PortAudio.

## Consequences

The project can now validate whether realtime processed guitar audition is useful and feels playable on the reference hardware before committing the full GUI to a replacement audio backend.

A successful experiment does not rehabilitate PortAudio ASIO for production. The production path still requires evidence of vendor-state preservation and reconnect recovery under ADR-058.

The presets are intentionally generic approximations and are not reproductions of Ubisoft/Rocksmith DSP.
