# ADR-047: Staged tone settings diff remains review-only

## Status

Accepted for implementation.

## Context

The local tone-reference workflow can now surface evidence, create an unapproved proposal, record explicit human accept/reject decisions, and stage accepted observations into the existing pending `ToneReviewArtifact`. Before final component and tone approval, a reviewer needs a compact comparison showing exactly what changed relative to the original pending review.

A diff artifact must not become a second approval channel. In particular, it must not mutate review state, set component decisions, mark a tone approved, or close the injection gate.

## Decision

Add a read-only staged-settings comparison between two `ToneReviewArtifact` documents that share the same song identity, catalog SHA-256, bound-plan SHA-256, arrangements, labels, and component structure.

The comparison records only changed device identity and knob values, plus a count of unchanged components. It rejects structural mismatches rather than attempting to align or infer components. It also rejects artifacts that are already injection-ready because the comparison is specifically a pre-approval review aid.

The operator command writes paired JSON and Markdown output beneath ignored `private/tone-reference-diffs/` by default.

The diff contract is explicit:

- `human_review_required = true`
- `can_approve = false`
- `can_inject = false`
- neither input review artifact is mutated
- final component and tone approval remains exclusively in the existing human tone-review workflow

## Safety and provenance

This feature reads only derived review metadata. It does not access or modify the live Rocksmith installation, inspect PSARC payloads, or persist commercial audio/DLC/Ubisoft-derived content. Generated diff artifacts remain private and ignored by Git.

## Consequences

Reviewers gain an auditable staged-vs-original view without weakening the established approval boundary. A later integration may require the reviewer to acknowledge this comparison before final approval, but that acknowledgement must still route through the existing explicit human approval functions rather than the diff itself.
