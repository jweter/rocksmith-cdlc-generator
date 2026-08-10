# ADR-007: Bass fret mapping is sequence optimization

## Context

A bass pitch can often be played at several string/fret locations. Choosing each note independently creates unnecessary position jumps, awkward string crossings, and unstable fingering. The project roadmap therefore requires fret mapping to optimize a sequence rather than perform a simple lookup.

## Decision

Represent each four-string bass tuning as the MIDI pitches of its open strings, ordered from lowest to highest. For every transcribed MIDI note, enumerate every playable string/fret candidate inside a configurable fret limit. Then use dynamic programming over each contiguous playable note sequence to choose the lowest-cost path.

The initial transition cost considers:

- absolute fret movement;
- number of strings crossed;
- a penalty for large fret jumps;
- a small high-fret bias;
- a small open-string preference.

The mapped artifact preserves alternate positions and carries a separate mapping-confidence value. Source transcription review flags propagate into mapping review. Notes that are impossible in the selected tuning/fret range are preserved as unmapped and force validation to FAIL.

## Alternatives

- Always choose the lowest available fret.
- Always choose the highest-pitched playable string.
- Greedy nearest-neighbor mapping based only on the previous note.
- Machine-learned fingering prediction.

## Reasons

Dynamic programming gives deterministic, explainable global optimization without requiring training data. It is fast enough for full songs and leaves room for future cost terms such as hand position, technique constraints, repeated-riff consistency, and known-good chart priors.

## Consequences

The initial cost function is a heuristic and must be benchmarked against human-authored arrangements. Mapping confidence is therefore kept distinct from pitch/timing confidence. Technique-aware mapping and phrase-level consistency can refine this layer later without changing the canonical note representation.
