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
- report the exact selected input/output endpoint, actual stream sample rate, input/output latency, peak level, and callback-status events;
- treat functional I/O and low-latency readiness as separate results;
- allow explicit host-API/device selection and fail closed when a required low-latency path is unavailable;
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

`--enable-asio` only exposes ASIO-capable PortAudio host APIs. It does not by itself guarantee that the stream actually uses ASIO.

For a strict ASIO4ALL qualification on the current reference laptop, use:

```text
python scripts/probe_scarlett_2i2.py --enable-asio --run --input-channel 1 --sample-rate 48000 --block-size 128 --host-api ASIO --device-name "ASIO4ALL v2" --require-selected-path
```

This command must either select the `ASIO4ALL v2 [ASIO]` full-duplex endpoint or fail. It may not silently fall back to MME, DirectSound, WASAPI, or WDM-KS.

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
3. Run endpoint enumeration.
4. Run the normal explicit monitor probe and record selected endpoint/latency/callback status.
5. Run the strict ASIO4ALL command above and confirm the selected endpoint printed by the script is `ASIO4ALL v2 [ASIO]`.
6. Verify the instrument is audible in both output channels.
7. Record the reported round-trip latency and callback-status count.
8. Repeat at 48 kHz with 64, 128, and 256 frame buffers if the path is stable.
9. Disconnect/reconnect the Scarlett and verify a fresh run resolves current endpoints again.

If ASIO4ALL opens but is not internally routed to the Scarlett, configure only the Scarlett input/output in the ASIO4ALL control panel before re-running. Do not alter the Rocksmith NoCableLauncher files as part of this qualification.

Hardware results stay private unless deliberately summarized without proprietary/private audio.

## Safety boundary

- never modify the live Rocksmith installation;
- do not modify the user's working NoCableLauncher configuration for this proof;
- no Real Tone Cable dependency;
- no background recording;
- no dry-DI capture in this proof slice;
- no committed hardware reports or audio;
- no commercial DLC/audio inspection;
- realtime monitoring starts only after the operator passes `--run`.

## Exit criteria

This proof is complete when the reference Windows machine can consistently enumerate the Scarlett, select Input 1/2, open a full-duplex monitor stream, produce visible input metering, report usable latency, and recover after device re-enumeration. If ASIO4ALL or another explicit low-latency path remains unacceptable, the next action is to replace/tune the Windows audio backend rather than build GUI monitoring on top of an unsuitable path.
