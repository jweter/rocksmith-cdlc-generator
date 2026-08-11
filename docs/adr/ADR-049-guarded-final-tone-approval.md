# ADR-049 — Guarded final tone approval orchestration

## Status
Accepted

## Context

The project now has an explicit human-reviewed chain from local tone-reference evidence through proposal, component accept/reject staging, staged-vs-original settings diff, and a final acknowledgement bound to the exact diff digest.

The existing `approve_component` and `approve_tone` functions correctly enforce human approval semantics, but a higher-level operator path must not allow those approvals to proceed against stale or changed staged settings.

## Decision

Add a guarded orchestration layer that requires all of the following before any approval action is executed:

1. the original pending tone review;
2. the current staged pending tone review;
3. the staged-settings diff that the reviewer inspected;
4. a valid final-review acknowledgement bound to that exact diff;
5. an explicit list of component and/or tone approval actions.

At execution time the guard recomputes the staged-vs-original diff and requires it to match the acknowledged diff exactly. It then verifies the acknowledgement against that current diff before delegating only the explicitly requested actions to the existing `approve_component` and `approve_tone` functions.

The orchestration request does not accept knob values or device substitutions. Settings must already be present in the staged review that the human inspected. Changing those settings requires regenerating the diff and obtaining a new acknowledgement.

## Safety properties

- No acknowledgement means no guarded approval.
- A stale acknowledgement cannot authorize changed staged settings.
- No approval action is inferred automatically.
- Duplicate actions fail closed.
- Tone approval still requires every component in that tone to be explicitly approved first.
- The existing `ready_for_injection` invariant remains authoritative.
- This layer never modifies the live Rocksmith installation and never reads or writes PSARC/commercial audio content.

## Consequences

The final tone-review workflow becomes auditable and deterministic while retaining human authority. The GUI can later invoke this same guard after the reviewer inspects and acknowledges the final staged-settings diff.

A future slice may bind live-audition/listening acknowledgement to the same staged-settings identity before allowing guarded approval for tone changes that require subjective listening review.
