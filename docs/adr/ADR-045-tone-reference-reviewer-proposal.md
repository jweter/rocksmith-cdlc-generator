# ADR-045: Tone-reference reviewer proposal artifact

## Status

Accepted for implementation.

## Context

The private local tone-reference workflow can now surface reviewer-facing evidence from verified local PSARC-derived metadata. The next useful operation is allowing a human to select a surfaced candidate or subset of its components for closer review without silently mutating the active bound tone plan.

## Decision

Introduce a separate `ToneReferenceReviewerProposal` artifact with these properties:

- It is built only from a previously generated `ToneRecommendationEvidenceReport`.
- Candidate selection is by arrangement plus the exact surfaced tone fingerprint.
- Optional component selection is limited to component slots already present on that candidate.
- Device keys and knob values are copied only from the evidence object; callers cannot supply replacement values through this API.
- The artifact records the bound-plan SHA-256 and a SHA-256 digest of the normalized evidence document.
- Copied knob values are named `observed_knob_values` to distinguish evidence from approved authoring settings.
- Proposal-level and component-level approval default to false.
- `can_auto_apply` and `can_inject` are always false in this slice.
- The proposal writer targets ignored private storage. No generated proposal is committed.

## Safety boundary

This feature does not read or write the live Rocksmith installation. It does not extract PSARCs, package DLC, mutate a `BoundRocksmithTonePlan`, approve a tone, or mark any value safe for injection. Commercial audio, Ubisoft-derived payloads, extracted manifests, and private proposals remain outside version control.

## Consequences

A reviewer can now deliberately stage observed reference settings into a traceable private document for comparison and audition. A later change may define an explicit review decision that promotes selected proposal values into the existing human-approved tone-review workflow, but that promotion must remain a separate action with validation and cannot be inferred from proposal creation.
