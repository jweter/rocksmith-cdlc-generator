# ADR-054: Require explicit low-latency audio path selection

## Status

Accepted

## Context

The first private Scarlett 2i2 probe proved full-duplex connectivity but reported roughly 106 ms round-trip latency. Enabling ASIO support caused ASIO endpoints to appear, but the resolver still selected ordinary Scarlett Windows endpoints because `--enable-asio` only exposed the host API; it did not force an ASIO stream.

This made an "ASIO test" ambiguous and could hide fallback to MME, DirectSound, WASAPI, or WDM-KS.

## Decision

Separate host-API availability from endpoint selection.

`AudioProbeRequest` may now carry a preferred host API and/or device-name substring plus a `require_preferred_path` flag.

When an explicit preferred path is requested:

- a matching full-duplex endpoint is selected when available;
- the same endpoint is used for input and output for bridge-style devices such as ASIO4ALL;
- the selected input/output endpoint is printed in the operator report; and
- `require_preferred_path=true` fails closed instead of silently falling back.

The current reference-machine next test uses the already-installed `ASIO4ALL v2 [ASIO]` endpoint. This does not modify the user's working Rocksmith NoCableLauncher configuration.

## Consequences

The hardware qualification can now answer the important question directly: whether a specific low-latency path is actually being exercised.

ASIO4ALL remains a bridge, not a permanent architectural commitment. If it is unstable, too latent, or cannot route the Scarlett reliably, the backend abstraction allows replacement without changing the higher-level audition contracts.

No audio is recorded. No Rocksmith files, launchers, drivers, DLC, or live installation contents are modified by this change.
