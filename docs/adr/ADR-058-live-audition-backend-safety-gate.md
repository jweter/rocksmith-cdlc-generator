# ADR-058: Gate production live audition on backend safety evidence

## Status

Accepted

## Context

The reference Scarlett 2i2 3rd Gen has proven that the native Focusrite ASIO driver can provide functional full-duplex guitar I/O with low reported latency. However, opening that ASIO path through PortAudio/python-sounddevice changed the buffer shown in Focusrite Device Settings. A second attempt using `blocksize=0` still changed the operator-selected buffer from 128 to 144 frames.

A future GUI must not equate a successful low-latency probe with production readiness. The audio backend also has to preserve vendor state and recover predictably when the interface is disconnected and reconnected.

## Decision

Add a backend-agnostic production eligibility gate in `audio_backend_policy.py`.

A backend is eligible for production Live Tone Test use only when all of the following are proven:

- functional full-duplex instrument I/O;
- the configured low-latency target;
- preservation of vendor driver state during normal opening/monitoring;
- device disconnect/reconnect recovery;
- no required opt-in to a potentially state-changing operation.

The policy fails closed and returns explicit blockers when any property is missing.

PortAudio native ASIO remains available for enumeration and explicitly opted-in controlled experiments, but the current evidence does not satisfy the production gate because vendor buffer preservation is false and stream opening requires a state-change opt-in.

## Consequences

- Future GUI code has a clear, testable contract before enabling live tone audition.
- A low-latency measurement alone cannot promote a backend to production status.
- The proven native Focusrite ASIO transport remains the preferred target, while the adapter implementation can be replaced without changing the policy.
- Hardware-specific evidence stays separate from the generic policy model.
- No Rocksmith, NoCableLauncher, driver, vendor control-panel, commercial audio, or DLC state is modified by this policy.
