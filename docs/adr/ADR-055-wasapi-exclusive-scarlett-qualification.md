# ADR-055: WASAPI Exclusive Scarlett Qualification

- Status: Accepted
- Date: 2026-08-11

## Context

The reference Windows laptop proved functional Scarlett 2i2 input/output through the existing PortAudio adapter, but the ordinary Windows path reported about 106.7 ms round-trip latency. A strict ASIO4ALL probe reduced reported round-trip latency to about 41.5 ms, but the run reported zero guitar input, so ASIO4ALL is not yet a qualified production path.

The working Rocksmith NoCableLauncher setup must remain untouched while the generator searches for a lower-latency audition path.

## Decision

Add an explicit `--wasapi-exclusive` qualification mode to the existing `SoundDeviceBackend` and operator probe.

When enabled:

1. The operator probe defaults the required host API to `Windows WASAPI`.
2. Preferred-path enforcement is mandatory; the run may not fall back to MME, DirectSound, WDM-KS, or ASIO.
3. The backend verifies both selected endpoints are WASAPI endpoints before validation or stream creation.
4. `sounddevice.WasapiSettings(exclusive=True)` is applied independently to input and output validation and to the full-duplex stream.
5. The probe remains explicit, short-lived, non-recording, and writes only the existing ignored private qualification report.
6. `--enable-asio` and `--wasapi-exclusive` are mutually exclusive probe modes.

## Rationale

WASAPI exclusive mode provides a low-latency comparison path using the Scarlett endpoints Windows already enumerates successfully. It does not require modifying the user's Focusrite driver stack, Rocksmith installation, or NoCableLauncher configuration.

The project should measure this path rather than infer that it will outperform ASIO4ALL. The selected production backend remains a measurement-driven decision.

## Consequences

- CI can verify the exclusive-mode contract with a fake sounddevice implementation but cannot prove physical latency.
- The next reference-machine measurement is Scarlett WASAPI exclusive at 48 kHz / 128 frames.
- A viable path must show functional full-duplex I/O, non-zero guitar input, stable callbacks, and preferably <=25 ms reported round-trip latency.
- If WASAPI exclusive remains unsuitable, the next action is a different Windows realtime backend or driver strategy rather than GUI integration.
