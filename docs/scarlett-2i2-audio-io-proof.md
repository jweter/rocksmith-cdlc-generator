# Scarlett 2i2 Windows Audio I/O Proof

## Goal

De-risk the future Live Tone Test before the full GUI depends on realtime audio.

The reference hardware is a Focusrite Scarlett 2i2 on Windows 11. Rocksmith's Real Tone Cable requirement is not part of this application: the generator talks to the local audio interface through a replaceable Windows audio backend.

## Proof scope

This slice proves the smallest useful hardware contract:

- enumerate current Windows audio endpoints;
- resolve Scarlett/Focusrite endpoints without persisting unstable numeric device IDs;
- exclude loopback endpoints from physical instrument selection;
- select physical Input 1 or Input 2;
- require a stereo output endpoint;
- validate sample rate and channel configuration before opening a stream;
- briefly monitor the selected mono instrument channel to both output channels;
- report actual stream sample rate, input/output latency, peak level, and callback-status events;
- treat functional I/O and low-latency readiness as separate results;
- re-enumerate on each run so reconnect/device renumbering can recover naturally.

No audio is written to disk by the monitor probe. Only a small JSON qualification report is written under ignored `private/` storage.

## Backend boundary

`AudioBackend` is deliberately independent of PortAudio or Qt. The first adapter is `SoundDeviceBackend`, using the optional `python-sounddevice` dependency.

This choice is a proof adapter, not a permanent architecture lock. If later private hardware testing shows that another Windows backend provides materially better Scarlett latency or device-loss handling, it can replace this adapter without changing the qualification model or GUI-facing contracts.

## Operator workflow

Install the optional audio dependency in the local environment, then enumerate endpoints without opening a stream:

```text
python scripts/probe_scarlett_2i2.py
```

Run an explicit short monitor probe on physical Input 1:

```text
python scripts/probe_scarlett_2i2.py --run --input-channel 1
```

Try the ASIO-capable PortAudio DLL exposed by current pip-installed `python-sounddevice` on Windows:

```text
python scripts/probe_scarlett_2i2.py --run --input-channel 1 --enable-asio
```

Input 2 is selected with `--input-channel 2`.

## Qualification interpretation

`qualified=true` means the requested full-duplex stream configuration opened and completed the monitor probe without an exception.

`low_latency_ready=true` is stricter: reported input + output latency is at or below the configured audition target, currently 25 ms by default.

A functionally correct but higher-latency result remains valuable. It proves connectivity while identifying latency as the next optimization problem rather than conflating the two.

Callback status events are surfaced as warnings because underflow/overflow conditions may indicate that the buffer is too aggressive or the host API/driver path needs adjustment.

## Manual private hardware qualification

The repository and CI cannot prove physical Scarlett behavior. The reference-machine acceptance check is manual/private:

1. Plug guitar or bass into Scarlett Input 1 or Input 2.
2. Route headphones/monitors through the Scarlett.
3. Run endpoint enumeration and confirm physical Scarlett endpoints are selected rather than loopback.
4. Run the explicit monitor probe.
5. Verify the instrument is audible in both output channels.
6. Record the reported round-trip latency and callback-status count.
7. Repeat with representative 48 kHz buffer sizes such as 64, 128, and 256 frames.
8. Disconnect/reconnect the Scarlett and verify a fresh run resolves the newly enumerated endpoint IDs.
9. Compare the normal backend and `--enable-asio` path where available.

Hardware results stay private unless deliberately summarized without proprietary/private audio.

## Safety boundary

- never modify the live Rocksmith installation;
- no Real Tone Cable dependency;
- no background recording;
- no dry-DI capture in this proof slice;
- no committed hardware reports or audio;
- no commercial DLC/audio inspection;
- realtime monitoring starts only after the operator passes `--run`.

## Exit criteria

This proof is complete when the reference Windows machine can consistently enumerate the Scarlett, select Input 1/2, open a full-duplex monitor stream, produce visible input metering, report usable latency, and recover after device re-enumeration. If latency is unacceptable, the next action is backend/driver tuning rather than GUI integration.
