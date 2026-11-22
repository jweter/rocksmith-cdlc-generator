# Octave leakage negative — canonical #796 slice 31

**Stage:** deterministic synthetic implementation; **not** real-song Bass
transcription, source isolation, false-positive-rate or gameplay proof.

## Why this gap matters

A low Bass score note (for example E1, MIDI 28 ≈41.20 Hz) can appear
compatible with a pitch estimate even when the observable recording contains
only its octave E2 (≈82.41 Hz). That E2 may come from a guitar, synth, organ,
overlapping drums or another non-Bass source, or it may be an actual harmonic
of an E1 instrument with an inaudible fundamental. **Octave energy alone
cannot establish a lower fundamental.** An arbitrary transcriber confidence
of 100% or a hash-bound, non-cloned, aligned stem is not independent pitch
truth.

Existing `bass_harmonic_evidence.py` already rejects missing-fundamental
E2-only examples as *ambiguous diagnostic evidence*; it is deliberately not
a source of automatic trusted notes. This new bounded negative detector
reuses its Hann-windowed PCM and Goertzel measurements without importing a
second model, running subprocesses, or reading private source content remotely.

## Measured negative-only rule

`inspect_bass_octave_leakage(audio_path, expected_midi, note_start_seconds,
note_duration_seconds)` samples two **non-overlapping 320-ms** PCM windows
inside a previously matched note's recorded span. A conservative
`octave_leakage` result requires **both** windows to have:

- a measurable non-silent signal with RMS ≥100 integer PCM units;
- a strong corresponding octave spectral component, normalized by the
  local full-window RMS/length (≥0.14);
- an octave/fundamental Goertzel-amplitude ratio of at least 8:1.

The detector returns one of `octave_leakage`, `not_detected`,
`insufficient_signal` (including short notes and missing independent
windows) or `unavailable` (invalid/corrupted/inaccessible source). None
asserts Bass instrument identity, pitch verification, source isolation,
recording timing or actual Rocksmith gameplay.

In the **real** `reconcile_project_bass` pipeline, the probe is injected
only after independently accepted Bass stem provenance, source hash,
noncloned identity, recording-clock agreement and negative silence/drum
screen. For a matched score event, a strong octave-only result appends
`OCTAVE_LEAKAGE_NEGATIVE`, preserves `review_required`, and prevents
`symbolic_verified` promotion regardless of self-reported pitch,
transcriber and alignment confidence. Unreadable octave-source windows
append `OCTAVE_SCREEN_UNAVAILABLE` and also fail closed. No independent
windows/short event means the new **negative** detector has insufficient
observations and cannot be treated as a positive pass, while established
matching/provenance gates continue to apply.

Reconciliation changes from v7 to **v8**, invalidating any cached Bass
charts produced without this additional matched-note veto. The public
report contains stable statuses and booleans only, never audio bytes,
private WAV paths, song names or process identities.

## Automated negative and control evidence

Original generated PCM fixtures, not private songs, cover E2-only and
stereo-polarity-inverted E2, true E1 fundamentals with E2 partials
(including a second harmonic louder than the fundamental), the adjacent
F1 semitone, silent and truncated PCM, short notes, missing files, invalid
MIDI/timing, unknown diagnostic verdicts, and deliberately forged
100%-confident E1 note predictions against an E2-only source.

The synthetic reconciliation adversary sets the *earlier* verified-stem
and score/timing gates green. Despite those conditions, an octave-negative
candidate is still `symbolic_unverified` with
`OCTAVE_LEAKAGE_NEGATIVE`. We also verify the negative diagnostic is
never invoked when source provenance is unverified and cannot itself grant
authority.

## Tradeoffs and unproven work

This rule deliberately prioritizes avoiding *false independent Bass
verification*, not transcription recall. True Bass notes with little
measured fundamental may conservatively remain review-only. Notes shorter
than about 0.74 seconds cannot fit the two long windows; no claim is made
for them. Multiple instrument mixtures, intermittent octave leakage,
phase-locked harmonic aliases, and all real-song source purity remain
research/evidence gaps. A matching score and an apparently present Bass
harmonic do not prove who played the source.

The historical approximately two-bar arrangement delay, E1/F1 real-song
accuracy, Lead/Rhythm equality, source rights, Windows Home offline
containment and Rocksmith gameplay are **not** resolved by this slice.
