# ADR-049 — Acknowledgement-gated tone approval

## Context

The tone-reference workflow now produces a staged `ToneReviewArtifact`, a deterministic staged-vs-original settings diff, and a separate human acknowledgement bound to the SHA-256 of that exact diff.

The acknowledgement is intentionally non-approving. A distinct operation is required to close the existing human tone-review gate.

Without a guarded orchestration layer, callers could invoke the lower-level `approve_component()` / `approve_tone()` primitives directly without proving that the current staged settings are the settings the reviewer actually inspected.

## Decision

Add a separate approval orchestration layer with these invariants:

1. The original and staged tone reviews must still be entirely pending.
2. The current staged diff is recomputed from the supplied original and staged reviews.
3. The recomputed diff digest must exactly match the supplied diff.
4. The final-review acknowledgement must validate against that exact current diff.
5. The approval operator identity must match the acknowledgement reviewer.
6. Approval requires an explicit confirmation flag/action.
7. Unresolved components cannot be approved.
8. Approval may change only decision/reviewer-note fields. Device keys, names, slots, families, and knob values must remain byte-for-byte equivalent at the model level to the acknowledged staged state.
9. A receipt records the acknowledged diff digest, reviewer, approved components/tones, and final injection-readiness state.

The acknowledgement itself retains `can_approve=false` and `can_inject=false`. It is merely a mandatory prerequisite for the distinct approval action.

## Alternatives considered

### Treat acknowledgement as approval

Rejected. This collapses inspection provenance and authoring approval into one artifact and weakens the explicit human-control boundary.

### Allow knob edits during final approval

Rejected. Any post-acknowledgement setting edit would mean the reviewer did not inspect the exact state being approved. Edits require regenerating the staged diff and acknowledgement.

### Continue exposing only the low-level approval primitives

Rejected as the preferred operator path. The primitives remain useful internally and in tests, but the local tone-reference workflow should use the guarded orchestration layer.

## Consequences

- Final tone approval becomes auditable and stale-review resistant.
- A changed device or knob value automatically invalidates the prior acknowledgement path.
- The resulting `ready_for_injection=true` review is still not permission to modify the live Rocksmith installation. Downstream Tone2014 serialization/package staging must continue to validate provenance and operate only in project/private staging.
- Commercial DLC/audio and Ubisoft-derived payloads remain local/private and are not committed.
