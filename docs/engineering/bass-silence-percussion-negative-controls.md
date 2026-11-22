# Bass silence/percussion-only negative controls — canonical #796 slice 28

Status: **bounded synthetic implementation; do not label real Bass as verified
until the independent source, rights and Product Reality conditions exist.**

## Failure mode

The real `is_verified_bass_stem_transcription` path checked a Bass-labeled
stem receipt, source SHA-256, PCM geometry, recording clock, nontrivial
difference from the original mix, and the transcription digest. These are
necessary provenance checks, but they did **not** prove the candidate waveform
contained a Bass instrument. For example, a click, kick-drum-only or nearly
silent file can have valid WAV geometry, distinct content and arbitrary
high-confidence, pitch-matching predicted notes. A high transcriber
confidence is self-reported candidate evidence, not independent musical truth.

## Negative-only source screen

`screen_bass_stem_obvious_negatives` reads only the explicit existing local
PCM file; it does not copy media or run inference. It examines up to twelve
distributed 480-ms windows, each made of six 80-ms subwindows, without
reading the entire full-length song into memory. Each short segment measures
DC-removed RMS on the louder channel to avoid stereo cancellation. A
non-negative candidate must contain at least four **consecutive** subwindows
above both an absolute RMS floor and a fraction of that window's observed
peak. A few isolated drum attacks cannot satisfy sustained-content evidence,
even if their waveform is loud and low-pitched.

The result is intentionally one-sided:

- `silence_only`: no meaningful signal in inspected windows — cannot
  independently verify Bass;
- `transient_only`: short attacks with no confirmed sustained region —
  cannot independently verify Bass;
- `unavailable`: missing, truncated, unreadable, unsupported or too-short
  audio — cannot independently verify Bass;
- `not_obviously_negative`: sufficient sustained audio is present to
  **avoid this particular veto**, but **Bass instrument identity,
  isolation, note pitch, recording timing and gameplay are still unproven**.

`is_verified_bass_stem_transcription` applies this veto in addition to all
existing stem provenance, content-clock and full-mix-clone checks, before the
production `reconcile_project_bass` path can admit a stem's predicted
notes. Reconciliation semantics advance to **v7**; prior v6 persisted
charts must be regenerated instead of implicitly retaining trust.

## Adversarial executable regressions

Tests synthesize only newly composed 8-kHz PCM: exact silence, DC-only audio,
repeated low-frequency kick transients, unrelated high-frequency drum
attacks, denser short kicks, and a genuinely sustained low-frequency
harmonic tone. Both mono and phase-inverted stereo cases are exercised.
In the critical test, pre-existing hash/clock/distinctness checks are
*deliberately simulated as successful* and the user-supplied pYIN-style
Bass candidate is assigned **100% pitch, timing and overall confidence**.
Silence and drum-only candidates still cannot obtain verified-stem
provenance: their per-note qualification retains `UNVERIFIED_STEM`.

Truncated RIFF data, missing files, invalid geometry and old v6
reconciliations also fail closed. The positive sustained-tone control proves
only that the negative screen does not reject **all** audio; it does not
simulate an AI separator or establish real Bass content.

## Known bounds and follow-ons

This is a **heuristic obvious-negative veto**, not an instrument-classifier:
sustained guitar, organ, bass-like synth, continuous resonant percussion,
or dense overlapping drum noise may contain enough sustained audio to evade
it. It can conservatively reject real short staccato Bass passages, silent
introductions or Bass that appears outside distributed sample windows.
Those should become explicit human-review items, never falsely promoted
notes. An independent legally sourced Bass truth benchmark, isolated
source-model licensing and actual musical/Product Reality tests remain
separate requirements; this slice does not repair the historical
two-measure timing offset.

No private audio, model, weights, filename or PID enters public test data.
