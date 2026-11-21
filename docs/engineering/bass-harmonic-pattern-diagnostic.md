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
