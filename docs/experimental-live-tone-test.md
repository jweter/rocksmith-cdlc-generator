# Experimental Live Tone Test

## Purpose

This is the first deliberately playable local guitar-audition slice. It is not yet the production Live Tone Test GUI.

It proves that a real guitar/bass signal can travel through the local Scarlett input, through the project's generic local DSP abstraction, and back to the Scarlett output so the operator can hear an altered tone.

No audio is recorded or written to disk.

## Current safety status

The reference Scarlett 2i2 3rd Gen has proven native `Focusrite USB ASIO` full-duplex operation and playable reported round-trip latency through the current PortAudio/sounddevice adapter. However, opening that adapter can change the buffer shown in Focusrite Device Settings.

Therefore this test is intentionally experimental:

- it is not production-backend eligible;
- it requires an explicit command-line acknowledgement before an ASIO stream opens;
- it does not imply approval of a Rocksmith tone;
- it does not modify Rocksmith or NoCableLauncher;
- it does not save audio;
- the operator must check Focusrite Device Settings after the run and restore the preferred buffer if it changed.

## First real-hardware playable validation

On 2026-08-11 the reference Windows laptop + Scarlett 2i2 3rd Gen successfully completed all three generic presets with audible processed guitar output:

| Preset | Reported round-trip latency | Peak input | Observed callback frames |
| --- | ---: | ---: | ---: |
| clean | 15.17 ms | 1.0000 | 144 |
| clean, second run | 17.83 ms | 1.0000 | 160 |
| crunch | 18.50 ms | 1.0000 | 176 |
| drive | 19.17 ms | 1.0000 | 192 |

The operator confirmed that the test was playable and all presets worked. This validates the first end-to-end playable milestone.

The same session also produced two important development findings:

1. `Peak input level: 1.0000` means the capture reached digital full scale. The live-tone command now reports input level health explicitly and warns the operator to reduce Scarlett input gain before judging tone quality.
2. Callback size increased across repeated PortAudio-ASIO runs (`144 -> 160 -> 176 -> 192`) while reported latency increased with it. This reinforces the existing decision that the PortAudio ASIO adapter is experimental and cannot become the production Live Tone Test backend until vendor-state preservation is proven.

## Before running

1. Plug guitar or bass into Scarlett Input 1 or Input 2.
2. Use `INST` mode for a directly connected guitar/bass.
3. Route headphones/monitors through the Scarlett.
4. Turn Scarlett Direct Monitor OFF so the audible signal is the software-processed path rather than the dry hardware path.
5. Set the desired Focusrite sample rate/buffer in Focusrite Device Settings. The current reference configuration is 48 kHz; the buffer may still be renegotiated by PortAudio during this experimental run.
6. Set Scarlett input gain conservatively. A peak at or above `0.99` is treated as clipping-risk evidence; `0.90-0.99` is reported as hot.

## Run

From the repository root after installing the optional audio dependency:

```text
py -3.12 scripts/live_tone_test.py --preset crunch --input-channel 1 --seconds 15 --acknowledge-asio-buffer-may-change
```

Available generic presets:

- `clean` — small clean gain boost;
- `crunch` — generic gain + soft clipping + output trim;
- `drive` — stronger generic gain + soft clipping + output trim.

These are intentionally generic open/local approximations. They are not Ubisoft/Rocksmith DSP models and are not claims that a specific Rocksmith device has been reproduced.

## What to listen for

The goal is simply to prove the end-to-end experience:

- guitar is audible through the Scarlett output;
- the selected preset audibly changes the signal;
- latency feels playable enough to continue development;
- no obvious clipping, stuttering, or callback errors occur.

The command prints selected ASIO device, reported round-trip latency, peak input level, input-level status, observed callback frames, and callback-status warnings.

If `Input level status: CLIPPING` appears, lower the Scarlett input gain before evaluating the preset. Capture clipping occurs before the project's DSP and cannot be repaired by downstream processing.

## After running

Open Focusrite Device Settings and check the buffer. If PortAudio changed it, restore the operator-preferred value manually.

Do not treat a successful listening test as a tone approval. The existing human review and final acknowledgement gates remain separate.

## Next step

The first playable path is now confirmed on hardware. Keep the session/DSP contract, but move the production GUI onto a Windows audio backend that can prove vendor-state preservation and reconnect recovery. In parallel, begin local Guitar Pro/MusicXML arrangement import so real owned tab sources can feed the preview/timing workflow.
