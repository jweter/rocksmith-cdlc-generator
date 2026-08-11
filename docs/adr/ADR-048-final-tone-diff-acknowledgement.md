# ADR-048: Final staged tone-diff acknowledgement

## Status

Accepted for implementation.

## Context

The private tone-reference workflow can now stage explicitly accepted local reference observations into a pending `ToneReviewArtifact` and produce a reviewer-facing diff against the original review. The next trust boundary is proving that a human inspected the exact diff before later approval functions are allowed to act.

A generic checkbox or free-form note is insufficient because the staged settings could change after review. The acknowledgement must therefore bind to the exact normalized diff content.

## Decision

Introduce a separate `ToneReferenceFinalReviewAcknowledgement` artifact that records:

- song identity;
- bound-plan SHA-256;
- tone-catalog SHA-256;
- SHA-256 of the exact normalized staged-settings diff;
- an explicit reviewer identity;
- an optional reviewer note; and
- fixed safety flags showing that acknowledgement is not approval and cannot permit injection.

Creation and verification fail closed when the diff does not require human review, when safety flags claim approval/injection capability, when reviewer identity is blank, or when the current diff digest no longer matches the acknowledgement.

## Safety boundary

This acknowledgement does not modify the live Rocksmith installation, does not read or write PSARC/audio/commercial payloads, does not mutate a tone review, does not approve a component or tone, and does not close the injection gate. Generated acknowledgement documents belong under ignored `private/` storage.

## Consequences

Later approval orchestration can require a valid acknowledgement tied to the exact staged diff before invoking the existing component/tone approval functions. Any change to staged settings invalidates the previous acknowledgement and requires fresh human review.
