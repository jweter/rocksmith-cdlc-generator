# ADR-056: Preserve vendor-managed ASIO buffer settings

## Status

Accepted

## Context

The reference Scarlett 2i2 3rd Gen now exposes a native `Focusrite USB ASIO` endpoint and completes a full-duplex guitar monitor probe. During the first native ASIO qualification, however, opening PortAudio with a non-zero `blocksize` changed the buffer shown by Focusrite Device Settings from the operator-selected value.

The qualification tool is intended to measure the current hardware/software path, not silently reconfigure the user's audio interface. This is especially important because the same interface is also used by an existing Rocksmith setup.

`python-sounddevice` documents `blocksize=0` as the host-selected/optimal callback size and recommends non-zero callback block sizes only when an algorithm truly requires fixed frame counts. For native ASIO qualification, the vendor driver's control panel is the authoritative place for the operator to choose the hardware buffer.

## Decision

When both selected endpoints use the ASIO host API, `SoundDeviceBackend` opens the callback stream with `blocksize=0` regardless of the generic probe request's `block_size` field.

The probe records the minimum and maximum callback frame counts actually delivered and displays them to the operator. The CLI explains that `--block-size` applies to non-ASIO probes; native ASIO buffer configuration remains under the vendor control panel.

Non-ASIO behavior is unchanged and may still use the requested callback block size.

## Consequences

- Native Focusrite ASIO qualification no longer intentionally requests a new callback/hardware buffer size through PortAudio.
- The operator can set 64/128/256 samples in Focusrite Device Settings and verify the probe leaves that choice intact.
- Observed callback frames become evidence rather than an assumption.
- Future realtime DSP must tolerate driver-chosen callback frame counts or add a separate internal buffering layer instead of using the hardware probe to force the ASIO device.
- The probe remains read/observe oriented and does not modify Rocksmith or NoCableLauncher state.
