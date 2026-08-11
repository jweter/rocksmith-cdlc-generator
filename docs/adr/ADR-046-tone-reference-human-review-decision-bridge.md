# ADR-046: Human tone-reference review decision bridge

## Status

Accepted for implementation.

## Context

Local Rocksmith tone-reference evidence and reviewer proposals are intentionally non-authoritative. A reviewer still needs a controlled way to say which proposed component observations are useful before those values enter the existing human tone-review workflow.

The bridge must not turn corpus similarity, source authority, or a proposal selection into final tone approval. It also must not mutate the bound tone plan or make any artifact injection-ready.

## Decision

Introduce a separate `ToneReferenceReviewDecision` artifact with an explicit `accepted` or `rejected` decision for every proposed component slot.

A decision is valid only when:

- every proposed slot receives exactly one explicit human decision;
- no unknown slot is referenced;
- the decision records the SHA-256 of the exact normalized proposal;
- the proposal and destination tone review refer to the same bound-plan SHA-256;
- the destination arrangement and target components are still pending.

Accepted components may copy the proposal's observed device key, device name, and knob values into the existing `ToneReviewArtifact`. Those copied values remain `pending`. Rejected components leave the tone review unchanged.

This bridge never marks a component or tone `approved`, never sets `ready_for_injection`, never changes the bound tone plan, and exposes no automatic-apply path. Final approval continues through the existing `tone_review` functions after a human inspects the staged result.

## Safety and data boundary

The command operates only on private derived JSON artifacts. Generated decisions and staged reviews default under the Git-ignored `private/` tree. No PSARC, commercial audio, Ubisoft-derived manifest payload, or extracted DLC content is written to the repository or to the live Rocksmith installation.

## Consequences

The workflow gains a traceable transition from local-reference proposal to human tone review without collapsing the distinction between "accepted as useful evidence" and "approved for injection." Proposal tampering or plan drift causes staging to fail closed.

## Next

After this bridge is stable, add a reviewer-facing summary/diff of staged-versus-original tone settings so final approval can be made from a concise auditable comparison before the existing injection gate is allowed to close.
