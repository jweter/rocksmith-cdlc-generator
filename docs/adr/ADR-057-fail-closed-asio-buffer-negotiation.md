# ADR-057: Fail closed before ASIO buffer negotiation

## Status

Accepted

## Context

Private hardware qualification on the reference Scarlett 2i2 3rd Gen showed that opening the native `Focusrite USB ASIO` path through PortAudio/python-sounddevice can change the buffer value shown in Focusrite Device Settings. This occurred both when an explicit callback block size was requested and after switching the stream to `blocksize=0`.

The qualification tool is intended to observe and validate the local audio path. It must not silently mutate vendor driver settings merely by running a probe.

## Decision

Native ASIO device enumeration remains available when ASIO support is enabled, but opening an ASIO monitoring stream through `SoundDeviceBackend` fails closed by default.

An operator may explicitly allow the known PortAudio negotiation behavior with `--allow-asio-buffer-negotiation` for a controlled experiment. The flag name and console output state that the vendor control-panel buffer may change.

Non-ASIO behavior is unchanged. WASAPI exclusive and other probe paths retain their existing contracts.

## Consequences

- The default native ASIO probe can no longer silently change the Focusrite buffer.
- Existing successful native ASIO measurements remain useful evidence that the hardware/driver path works, but PortAudio is not yet accepted as the production native-ASIO adapter.
- A future Windows audio backend should preserve vendor buffer state or expose any requested driver change as an explicit operator action.
- Enumeration and diagnostics can continue without opening an ASIO stream.
