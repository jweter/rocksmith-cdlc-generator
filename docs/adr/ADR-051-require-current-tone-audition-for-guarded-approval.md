# ADR-051 — Require current tone audition for guarded approval when policy demands it

## Status
Accepted for implementation.

## Context

The project already records two separate human artifacts before final tone approval:

1. a final-review acknowledgement bound to the exact staged-vs-original settings diff; and
2. a tone-audition acknowledgement recording whether a human actually heard those exact staged settings and judged them `sounds_right` or `needs_revision`.

Those artifacts were intentionally non-authorizing. The next requirement is to let the approval path enforce listening when the workflow policy calls for subjective audition, without making audition mandatory for every legacy/test workflow before the Live Tone Test hardware path is available.

## Decision

Add an explicit `ToneApprovalPolicy` to guarded final approval.

When `require_current_audition` is false, existing guarded approval behavior remains unchanged.

When `require_current_audition` is true, approval must fail closed unless:

- a tone-audition acknowledgement is supplied;
- it validates against the exact current staged-settings diff;
- it confirms human listening;
- its safety flags do not grant approval or injection; and
- its decision is exactly `sounds_right`.

A `needs_revision` audition blocks all requested approval actions. Any staged-setting change invalidates the reviewed diff before either acknowledgement can authorize progress.

The approval request still cannot supply replacement device keys or knob values. It only identifies explicit component/tone approval actions after all configured gates pass.

## Safety consequences

- Listening evidence cannot approve anything by itself.
- Stale listening evidence cannot authorize changed settings.
- A negative listening result blocks approval.
- Final component/tone approval remains explicit and human-controlled.
- No live Rocksmith files, PSARC payloads, commercial audio, or Ubisoft-derived DSP are accessed.

## Hardware roadmap consequence

The next high-value de-risking slice after this policy bridge is a standalone Scarlett 2i2 Windows audio-I/O proof. That proof should happen before the full GUI implementation so the project can validate device enumeration, Input 1/2 capture, stereo monitoring, sample-rate/buffer behavior, reconnect handling, and practical latency without coupling those findings to the Song Workspace UI.
