# ADR-041: Explainable local tone-corpus diagnostics

## Status

Accepted

## Context

The private local tone-reference library can contain thousands of tones across official Rocksmith DLC, community CDLC, and user-created material. Before those references influence automatic tone recommendations, operators need two things: measurable corpus coverage and a transparent explanation of why any candidate ranked highly.

A scalar similarity score by itself is insufficient evidence because authority weighting, device-key overlap, descriptors, duplicates, and arrangement role all affect interpretation.

## Decision

Add a read-only diagnostic layer over the private local tone-reference library.

The corpus summary reports package count, tone count, official-tone count, source and arrangement distributions, unique tone-chain fingerprints, duplicate-chain count, device-key frequencies, and descriptor frequencies.

Similarity diagnostics preserve the existing ranking formula and expose its contributing evidence: authority weight, requested-device overlap, requested-descriptor overlap, matched device keys, and matched descriptors. Lead, Rhythm, and Bass remain strictly isolated.

Diagnostics are derived only from the private normalized library. They do not read or modify the live Rocksmith installation and do not export commercial package contents.

## Safety and trust boundary

- Diagnostic output is evidence, not approval.
- A high-ranked local reference cannot bypass the existing human tone-review gate.
- Official source authority remains higher than community CDLC when match evidence is otherwise equal.
- Duplicate fingerprints are reported rather than silently treated as independent evidence.
- No commercial audio, PSARC payload, extracted manifest, or Ubisoft-derived binary content is committed.

## Consequences

The first real DLC scan can be evaluated quantitatively before local references are connected to automated tone recommendations. Ranking behavior becomes inspectable and testable instead of opaque.
