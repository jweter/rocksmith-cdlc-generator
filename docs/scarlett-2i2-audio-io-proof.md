# Scarlett 2i2 Windows Audio I/O Proof

## Goal

De-risk the future Live Tone Test before the full GUI depends on realtime audio.

The reference hardware is a Focusrite Scarlett 2i2 3rd Gen on Windows 11. Rocksmith's Real Tone Cable requirement is not part of this application: the generator talks to the local audio interface through a replaceable Windows audio backend.

## Proof scope

This slice proves the smallest useful hardware contract:

- enumerate current Windows audio endpoints;
- resolve Scarlett/Focusrite endpoints without persisting unstable numeric device IDs;
- exclude loopback endpoints from physical instrument selection;
- select physical Input 1 or Input 2;
- require a stereo output endpoint;
- validate sample rate and channel configuration before opening a stream;
- briefly monitor the selected mono instrument channel to both output channels;
- report the exact selected input/output endpoint, actual stream sample rate, input/output latency, peak level, callback-status events, and observed callback frame size;
- treat functional I/O and low-latency readiness as separate results;
- allow explicit host-API/device selection and fail closed when a required low-latency path is unavailable;
- support an explicit Windows WASAPI exclusive probe that cannot fall back to another host API;
- preserve vendor-driver buffer settings for ASIO instead of requesting a hardware callback size through PortAudio;
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

For the preferred native Focusrite path on the reference laptop, first set the desired sample rate and buffer in Focusrite Device Settings, then run:

```text
python scripts/probe_scarlett_2i2.py --enable-asio --run --input-channel 1 --sample-rate 48000 --host-api ASIO --device-name "Focusrite USB ASIO" --require-selected-path --seconds 5
```

For ASIO streams the probe intentionally opens PortAudio with `blocksize=0`. That leaves callback sizing under the ASIO driver/host instead of trying to impose the CLI `--block-size` value on the interface. The probe reports observed callback frames so the operator can compare what the stream actually delivered with the setting visible in Focusrite Device Settings. The `--block-size` option remains meaningful for non-ASIO probes only.

For a strict ASIO4ALL qualification, use the same explicit host/device selection with `--device-name "ASIO4ALL v2"`. This path is retained only as a compatibility fallback; the native Focusrite driver is preferred when available.

For a strict Scarlett WASAPI exclusive qualification, use:

```text
python scripts/probe_scarlett_2i2.py --wasapi-exclusive --run --input-channel 1 --sample-rate 48000 --block-size 128 --seconds 5
```

The probe automatically requires `Windows WASAPI` when `--wasapi-exclusive` is set. On Windows, the Scarlett may appear as separate WASAPI capture and render endpoints rather than one full-duplex endpoint. Strict selection therefore accepts a matched Scarlett input/output pair on the requested host API while still rejecting Realtek, Intel, loopback, or mixed-device fallbacks. `python-sounddevice` applies `WasapiSettings(exclusive=True)` to both validation and the duplex stream, so this remains a real exclusive-mode qualification rather than a shared-mode label.

Input 2 is selected with `--input-channel 2`.

## Qualification interpretation

`qualified=true` means the requested full-duplex stream configuration opened and completed the monitor probe without an exception.

`low_latency_ready=true` is stricter: reported input + output latency is at or below the configured audition target, currently 25 ms by default.

A functionally correct but slightly higher-latency result remains valuable. It proves connectivity while identifying latency/reporting as the next optimization problem rather than conflating the two.

Callback status events are surfaced as warnings because underflow/overflow conditions may indicate that the buffer is too aggressive or the host API/driver path needs adjustment.

## Reference-machine measurements

The reference Windows 11 laptop has now established the following progression:

- ordinary Windows path: functional guitar I/O at about 106.7 ms reported round-trip latency;
- ASIO4ALL: about 41.5 ms, but the measured run reported zero guitar input;
- WASAPI exclusive: selected the correct Scarlett endpoints but PortAudio failed to open the duplex stream;
- WDM-KS: selected the correct Scarlett endpoints but PortAudio failed to open the duplex stream;
- native `Focusrite USB ASIO`: functional full-duplex guitar I/O, non-zero peak input (`0.3056` in the measured run), with PortAudio reporting about 25.83 ms round-trip latency while Focusrite Device Settings reported a lower driver-level round-trip figure.

The native Focusrite path is therefore the preferred production candidate. The remaining work is to measure it without mutating the driver's selected buffer size and reconcile the difference between driver-panel and PortAudio latency reporting.

## Manual private hardware qualification

The repository and CI cannot prove physical Scarlett behavior. The reference-machine acceptance check is manual/private:

1. Plug guitar or bass into Scarlett Input 1 or Input 2 and select instrument mode for a directly connected instrument.
2. Route headphones/monitors through the Scarlett and disable direct monitoring when measuring software-path latency.
3. Set sample rate and buffer size in Focusrite Device Settings.
4. Run endpoint enumeration and confirm `Focusrite USB ASIO [ASIO]` is present.
5. Run the strict native Focusrite ASIO command above.
6. Confirm selected input/output are the same native ASIO endpoint.
7. Verify non-zero instrument peak, audible monitoring, and no callback-status warnings.
8. Confirm the Focusrite control-panel buffer remains unchanged after the probe.
9. Record PortAudio round-trip latency and observed callback frames.
10. Repeat controlled measurements only after the stable 48 kHz baseline is established.

Hardware results stay private unless deliberately summarized without proprietary/private audio.

## Safety boundary

- never modify the live Rocksmith installation;
- do not modify the user's working NoCableLauncher configuration for this proof;
- do not silently change the Focusrite driver's sample-rate or buffer configuration during a qualification run;
- no Real Tone Cable dependency;
- no background recording;
- no dry-DI capture in this proof slice;
- no committed hardware reports or audio;
- no commercial DLC/audio inspection;
- realtime monitoring starts only after the operator passes `--run`.

## Exit criteria

This proof is complete when the reference Windows machine can consistently enumerate the native Focusrite ASIO endpoint, select Input 1/2, open a full-duplex monitor stream, produce visible input metering, preserve the operator-selected driver buffer, report usable latency, and recover after device re-enumeration. The GUI should build on the native ASIO path only after that contract is stable.
