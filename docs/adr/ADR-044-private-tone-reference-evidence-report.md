# ADR-044: Private tone-reference evidence reports

## Status

Accepted

## Context

The local tone-reference corpus can now surface same-arrangement reference candidates that share resolved Rocksmith device keys with a bound tone plan. That evidence is useful to an operator, but the project must not blur the boundary between observing a reference and approving or applying it.

The local library also contains provenance derived from the user's installed Rocksmith packages. Generated evidence artifacts therefore belong in private, ignored storage rather than the repository.

## Decision

Add an operator-facing report command that consumes only:

1. an already bound Rocksmith tone-plan JSON document; and
2. the normalized private local tone-reference library.

The command creates a machine-readable JSON evidence artifact and a human-readable Markdown companion. Its default destination is `private/tone-reference-evidence/`, which is already ignored by Git.

Reports expose candidate source authority, PSARC provenance, similarity score, matching device keys, component slots, and observed knob values. They state prominently that evidence is review-only and that automatic apply is not permitted.

The report path deliberately has no function that mutates a bound tone plan, copies candidate knob values into it, approves components, or marks a tone safe for injection.

## Consequences

- An operator can inspect local empirical evidence without reading raw library JSON.
- Evidence artifacts remain private by default.
- Recommendation provenance is preserved for later review decisions.
- A future proposal workflow may copy explicitly selected candidate settings into a separate review artifact, but that workflow must remain human-gated and must not auto-approve injection.
