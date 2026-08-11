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
- fail closed before native ASIO stream opening when the adapter cannot prove vendor-driver state preservation;
- re-enumerate on each run so reconnect/device renumbering can recover naturally.

No audio is written to disk by the monitor probe. Only a small JSON qualification report is written under ignored `private/` storage.

## Backend boundary

`AudioBackend` is deliberately independent of PortAudio or Qt. The first adapter is `SoundDeviceBackend`, using the optional `python-sounddevice` dependency.

This choice is a proof adapter, not a permanent architecture lock. Private hardware testing has proven that native Focusrite ASIO can provide functional low-latency full-duplex guitar I/O, but PortAudio stream opening can also change the vendor control-panel buffer. Therefore PortAudio native ASIO is an experimental measurement path, not yet a production Live Tone Test backend.

`audio_backend_policy.py` provides a separate production gate. A backend is not production-eligible until functional full-duplex I/O, low latency, vendor-state preservation, and reconnect recovery are all proven without requiring an opt-in to a potentially state-changing operation.

## Operator workflow

Install the optional audio dependency in the local environment, then enumerate endpoints without opening a stream:

```text
python scripts/probe_scarlett_2i2.py --enable-asio
```

Enumeration is safe and should show `Focusrite USB ASIO [ASIO]` when the native Focusrite driver is available.

Native ASIO stream opening through `SoundDeviceBackend` is blocked by default. This command intentionally fails closed before opening the stream:

```text
python scripts/probe_scarlett_2i2.py --enable-asio --run --input-channel 1 --sample-rate 48000 --host-api ASIO --device-name "Focusrite USB ASIO" --require-selected-path --seconds 5
```

A controlled hardware experiment may explicitly allow PortAudio ASIO buffer negotiation:

```text
python scripts/probe_scarlett_2i2.py --enable-asio --allow-asio-buffer-negotiation --run --input-channel 1 --sample-rate 48000 --host-api ASIO --device-name "Focusrite USB ASIO" --require-selected-path --seconds 5
```

**Warning:** `--allow-asio-buffer-negotiation` is deliberately named as an unsafe-for-production opt-in. Reference hardware testing showed that PortAudio can change the buffer displayed by Focusrite Device Settings even when the stream uses `blocksize=0`. Record the control-panel value before and after any controlled experiment and restore it manually if PortAudio changes it. Do not use this opt-in as the normal GUI/live-audition path.

For a strict ASIO4ALL experiment, use the same explicit host/device selection with `--device-name "ASIO4ALL v2"` and the same explicit negotiation opt-in. ASIO4ALL is retained only as a compatibility experiment, not a production candidate on the reference machine.

For a strict Scarlett WASAPI exclusive qualification, use:

```text
python scripts/probe_scarlett_2i2.py --wasapi-exclusive --run --input-channel 1 --sample-rate 48000 --block-size 128 --seconds 5
```

The probe automatically requires `Windows WASAPI` when `--wasapi-exclusive` is set. On Windows, the Scarlett may appear as separate WASAPI capture and render endpoints rather than one full-duplex endpoint. Strict selection therefore accepts a matched Scarlett input/output pair on the requested host API while still rejecting Realtek, Intel, loopback, or mixed-device fallbacks. `python-sounddevice` applies `WasapiSettings(exclusive=True)` to both validation and the duplex stream, so this remains a real exclusive-mode qualification rather than a shared-mode label.

Input 2 is selected with `--input-channel 2`.

## Qualification interpretation

`qualified=true` means the requested full-duplex stream configuration opened and completed the monitor probe without an exception.

`low_latency_ready=true` is stricter: reported input + output latency is at or below the configured audition target, currently 25 ms by default.

Neither flag by itself means the backend is production-safe. Production Live Tone Test eligibility is separately gated by `audio_backend_policy.py`, including vendor-state preservation and reconnect recovery.

Callback status events are surfaced as warnings because underflow/overflow conditions may indicate that the buffer is too aggressive or the host API/driver path needs adjustment.

## Reference-machine measurements

The reference Windows 11 laptop has established the following progression:

- ordinary Windows path: functional guitar I/O at about 106.7 ms reported round-trip latency;
- ASIO4ALL: about 41.5 ms, but the measured run reported zero guitar input;
- WASAPI exclusive: selected the correct Scarlett endpoints but PortAudio failed to open the duplex stream;
- WDM-KS: selected the correct Scarlett endpoints but PortAudio failed to open the duplex stream;
- native `Focusrite USB ASIO`, explicit 128-frame request: functional full-duplex guitar I/O, real guitar input, but PortAudio changed the Focusrite control-panel buffer to 256;
- native `Focusrite USB ASIO`, `blocksize=0`: functional full-duplex guitar I/O, `15.17 ms` reported round-trip latency, peak input `0.5354`, and observed callbacks of `144` frames, but the Focusrite control-panel buffer changed from 128 to 144.

The native Focusrite driver is therefore the preferred transport target, while the current PortAudio ASIO adapter is not production-eligible. The next backend must preserve the operator-selected vendor state as well as the already-proven low-latency/full-duplex behavior.

## Manual private hardware qualification

The repository and CI cannot prove physical Scarlett behavior. Controlled reference-machine checks remain manual/private:

1. Plug guitar or bass into Scarlett Input 1 or Input 2 and select instrument mode for a directly connected instrument.
2. Route headphones/monitors through the Scarlett and disable direct monitoring when measuring software-path latency.
3. Record the current sample rate and buffer in Focusrite Device Settings.
4. Run safe endpoint enumeration and confirm `Focusrite USB ASIO [ASIO]` is present.
5. Use the explicit `--allow-asio-buffer-negotiation` command only when intentionally running a controlled PortAudio experiment.
6. Confirm selected input/output are the same native ASIO endpoint.
7. Record non-zero instrument peak, audible monitoring, callback-status warnings, latency, and observed callback frames.
8. Re-open Focusrite Device Settings immediately after the experiment and record whether its buffer changed.
9. Restore the intended vendor setting manually if the experiment changed it.
10. Never treat a state-changing result as production-backend qualification.

Hardware results stay private unless deliberately summarized without proprietary/private audio.

## Safety boundary

- never modify the live Rocksmith installation;
- do not modify the user's working NoCableLauncher configuration for this proof;
- do not silently change the Focusrite driver's sample-rate or buffer configuration during a normal qualification run;
- native ASIO stream negotiation is blocked by default in the PortAudio adapter;
- controlled state-changing experiments require explicit operator opt-in;
- no Real Tone Cable dependency;
- no background recording;
- no dry-DI capture in this proof slice;
- no committed hardware reports or audio;
- no commercial DLC/audio inspection.

## Exit criteria

The audio transport proof is ready for GUI integration only when a backend can consistently enumerate the native Focusrite path, select Input 1/2, open a full-duplex monitor stream, produce visible input metering, meet the latency target, preserve the operator-selected vendor state, and recover after device re-enumeration. Until then, the GUI must not silently promote the experimental PortAudio native-ASIO path to production Live Tone Test status.
