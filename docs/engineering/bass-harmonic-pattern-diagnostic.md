# Bass harmonic pattern evidence — diagnostic-only long-window experiment

Status: deterministic pilot for issue #796 slices 29–31; no claim of
instrument isolation, verified transcription or automatic note selection.

## Problem

The Arrangement Preview's existing 0.18-second log-frequency spectrum is
for listening/visualization. At E1 (MIDI 28, ~41.203 Hz), the F1 semitone
(MIDI 29) is only ~2.45 Hz higher. A simple short-time spectral peak cannot
reliably distinguish adjacent low Bass notes under overlapping instruments.

## Conservative starting contract

`measure_bass_harmonic_pattern()` accepts an explicit source WAV,
expected MIDI pitch, **confirmed 4/5/6-string Bass tuning**, exact note time
and duration. It examines two nonoverlapping 0.65-second windows inside a
single sufficiently long sustained event. It measures the candidate's F0,
2×, 3× and 4× harmonics using Hann-weighted Goertzel on the stronger
stereo channel, compares aggregate energy with physically playable
adjacent semitones and octaves, and requires the fundamental itself to
remain sufficiently present.

Possible outcomes:
- `plausible_pattern`: at least two harmonics present in **both** windows,
  with original F0 sufficiently strong and ≥1.75× margin over the
  strongest considered competitor in each window.
- `ambiguous`: pitch mixture, octave confusion, insufficient margin,
  missing fundamental or no separable competitor.
- `insufficient_signal`: too-short note, silent window or incomplete
  two-window coverage.
- `unplayable`: no confirmed tuning or expected pitch cannot be
  physically played on the stated instrument.
- `unavailable`: unreadable, truncated or mutated WAV.

This algorithm requires longer sustained passages (≥1.4 seconds at the
default window length); normal short notes often produce
`insufficient_signal`. That is intentional rather than guessing. The
sample geometry and source SHA are checked with no remote media transfer.

**Theoretical candidate pitch != measured fundamental:** returned
`candidate_fundamental_hz` is calculated from the supplied MIDI number.
The output contains only evidence for/against that candidate. The
`note_pitch_verified`, `source_isolation_proven`,
`recording_timing_verified`, and `score_authority_changed`
flags remain false even for `plausible_pattern`.

The first tests use entirely original synthetic E1 and F1 tones with
harmonics, E2-only octave confusion, E1+F1 overlap, silent windows,
transient kick-like sound, out-of-phase stereo and insufficient tuning.
No private song or Bass model is needed.

## Limits and next proofs

A concurrent guitar, synthesizer, keyboard, or harmonically related
source can produce the same harmonic series. Even two windows and a
successful F0 ratio do **not** prove which instrument played a pitch.
Distortion and missing fundamentals can cause false negatives. A longer
window increases pitch resolution but decreases timing precision.
Do not use this diagnostic to move onset times, override source
notation, accept polyphonic chords or rewrite notes without the
independent source, role, recording-clock, provenance and product
verification gates.

After CI, integrate candidate display into the existing selected-note
evidence pane with explicit `review_only` labeling and run it via
background worker and source-hash cache. Test short actual Bass notes
and false positives on lawful real separated recordings before
promoting any automatic transcription.

## Canonical #796 slice 31 — octave-leakage negative (2026-11-21)

**Failure mechanism.** The earlier E1 Goertzel candidate aggregated the magnitudes
at the first four integer harmonic positions and required two stationary
windows, a root-to-largest-partial ratio of at least 0.25, more than one
supported harmonic and a 1.75x candidate/rival margin. A nearly missing
lower E1 fundamental could still acquire an apparently excellent E1
candidate margin by borrowing unrelated energy at E2, E3, and E4.
This is not independent proof that the Bass string sounded E1.

**Correction.** The same read-only `measure_bass_harmonic_pattern` path
now requires the actual E1 first-harmonic magnitude to be at least
**0.55 times its E2 second-harmonic magnitude** in both disjoint measured
windows. Otherwise the result is `ambiguous` with an explicit
`octave_leakage_negative` flag and the diagnostic
`minimum_root_to_octave_ratio`. Existing tuning/playability,
stationarity, nearby semitone/octave competitor and source-digest gates
continue to apply. Synthetic negative: E1/E2/E3/E4 amplitudes
1500/5000/4000/2000; the former summed E1 candidate margin exceeded
1.75 but the root-to-octave ratio is only 0.30 and is now rejected.
Synthetic positive *diagnostic control*: amplitudes 3600/5000/2000/1400
retain a lower root ratio 0.72 and a plausible harmonic pattern.

**This cannot prove instrument role**: an organ, distorted guitar, synth,
or other instrument can contain the same partial series. Even positive
`plausible_pattern` must keep `note_pitch_verified=false`,
`source_isolation_proven=false`,
`recording_timing_verified=false`, and
`score_authority_changed=false`. No stem, model or private recording
is touched; the score and arrangement are unmodified. The 0.55 floor
is an intentionally conservative fixture-based **negative only**, not an
empirically calibrated probability of correct Bass on real songs.
