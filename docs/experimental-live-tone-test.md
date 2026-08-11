# Experimental Live Tone Test

## Purpose

This is the first deliberately playable local guitar-audition slice. It is not yet the production Live Tone Test GUI.

It proves that a real guitar/bass signal can travel through the local Scarlett input, through the project's generic local DSP abstraction, and back to the Scarlett output so the operator can hear an altered tone.

No audio is recorded or written to disk.

## Current safety status

The reference Scarlett 2i2 3rd Gen has already proven native `Focusrite USB ASIO` full-duplex operation and approximately 15 ms reported round-trip latency through the current PortAudio/sounddevice adapter. However, opening that adapter can change the buffer shown in Focusrite Device Settings.

Therefore this test is intentionally experimental:

- it is not production-backend eligible;
- it requires an explicit command-line acknowledgement before an ASIO stream opens;
- it does not imply approval of a Rocksmith tone;
- it does not modify Rocksmith or NoCableLauncher;
- it does not save audio;
- the operator must check Focusrite Device Settings after the run and restore the preferred buffer if it changed.

## Before running

1. Plug guitar or bass into Scarlett Input 1 or Input 2.
2. Use `INST` mode for a directly connected guitar/bass.
3. Route headphones/monitors through the Scarlett.
4. Turn Scarlett Direct Monitor OFF so the audible signal is the software-processed path rather than the dry hardware path.
5. Set the desired Focusrite sample rate/buffer in Focusrite Device Settings. The current reference configuration is 48 kHz; the buffer may still be renegotiated by PortAudio during this experimental run.

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

The command prints selected ASIO device, reported round-trip latency, peak input level, observed callback frames, and callback-status warnings.

## After running

Open Focusrite Device Settings and check the buffer. If PortAudio changed it, restore the operator-preferred value manually.

Do not treat a successful listening test as a tone approval. The existing human review and final acknowledgement gates remain separate.

## Next step

Once this first playable path is confirmed on hardware, move the same GUI-facing/session contract onto a Windows audio backend that can prove vendor-state preservation and reconnect recovery. Only a backend passing the live-audition safety gate may become the default production GUI path.
