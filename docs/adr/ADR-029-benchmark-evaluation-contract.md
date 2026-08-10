# ADR-029: Benchmark evaluation contract

## Status

Accepted

## Context

The generator now has strong validation, packaging, provenance, and PSARC inspection boundaries, but those checks do not measure whether generated music authoring is accurate or whether it saves a human time. Future transcription, fretboard mapping, chord, technique, tone/effect, and review-workflow changes need a stable evaluation contract so improvements can be measured rather than judged impressionistically.

## Decision

Introduce a neutral `BenchmarkChart` representation and deterministic evaluator.

A benchmark note contains timing, MIDI pitch, optional physical string/fret, techniques, and explicit review/unresolved state. Reference and predicted charts share a `case_id`, arrangement role, and audio duration.

Musical note identity is matched independently from fretboard position. A note pair matches when MIDI pitch is identical and onset difference is within the configured tolerance. Matching is one-to-one and greedily minimizes onset error. This prevents a wrong string choice from being counted as a transcription failure while still exposing that error through the separate string/fret metric.

The evaluator records:

- note precision, recall, and F1
- onset and duration mean absolute error
- physical string/fret accuracy on comparable matched notes
- technique precision, recall, and F1 on matched notes
- review-required count and ratio
- unresolved count and ratio
- optional measured human editing time
- editing minutes per finished minute

Suite reports use macro averages so long/dense songs do not silently dominate smaller benchmark cases.

## Human productivity metric

`editing minutes per finished minute` is the principal product metric. It is computed from measured correction-session time divided by the benchmark excerpt duration. It must come from an actual editing session, not a retrospective estimate.

A model can therefore improve pitch F1 while still failing the product goal if it creates so many bad fret choices, techniques, or review flags that correction time rises.

## Tone and effects

Tone/effect reconstruction is deliberately treated as a separate evaluation dimension rather than folded into note accuracy. A mastered recording usually does not uniquely identify the exact physical amp, cabinet, pedal, microphone, or parameter settings that created a guitar sound.

A future tone benchmark should therefore score increasingly specific levels of correctness:

1. broad tone class: clean, edge-of-breakup, crunch, high-gain, fuzz-like, acoustic-like
2. effect-family presence: distortion/overdrive/fuzz, compression, wah/filter, chorus/flanger/phaser, delay, reverb, tremolo and similar modulation
3. coarse parameter similarity where measurable, such as gain amount, delay-time region, modulation depth/rate, and wet/dry balance
4. Rocksmith tone-component mapping and human similarity rating

Low-confidence tone inference must remain reviewable and must not claim a historically exact rig when the audio only supports an approximate playable tone.

## Corpus policy

The benchmark corpus should begin with 5–10 trusted 30–90 second excerpts covering simple and difficult Bass, Lead, Rhythm, alternate tunings, chords, techniques, and noisy mixes. Commercial recordings, proprietary tabs, and commercial Rocksmith packages remain local/private and are not committed to Git.

## Consequences

Future model and algorithm work gets measurable before/after evidence. The benchmark can distinguish whether a regression came from transcription, timing, fretboard mapping, techniques, review burden, or eventually tone/effect reconstruction.

The evaluator does not itself improve music generation. It establishes the scoreboard used to decide whether future changes actually help.
