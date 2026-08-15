# Reviewed Physical Position Editing v1

## Purpose

This milestone adds the first direct arrangement correction action to Song Workspace: explicit human acceptance of a string/fret position for a review-required Bass, Lead, or Rhythm source event.

The correction layer is deliberately separate from imported score/fan-out data. A user action records a reviewed overlay; it never rewrites the registered score or normalized fan-out JSON.

## Authority model

`review/reviewed_positions.json` is bound to:

- the registered complete-score SHA-256;
- the registered score format;
- the exact current score-fan-out manifest path and SHA-256;
- arrangement role;
- human-confirmed source track index;
- stable source event index;
- original source event start time and MIDI pitch.

A stored decision is rejected if any of those identities drift.

## Human action

From the Arrangement Preview review queue, the user may enter:

- a 1-based string number;
- a fret number;
- **Accept Position**.

Acceptance validates the proposed position against the arrangement's explicit source tuning. The selected string's tuning MIDI value plus fret must equal the source event MIDI pitch. Invalid or out-of-range positions are refused.

Only physical placement is accepted. This action does **not** confirm:

- source rights/provenance;
- Bass/Lead/Rhythm score mapping;
- note pitch or duration;
- shared timing;
- techniques;
- overall note trust/confidence;
- validation state;
- tone decisions;
- package readiness.

## Preview behavior

The synchronized arrangement preview overlays current reviewed positions after revalidating their provenance. The fretboard therefore shows the accepted physical placement without mutating the source score projection.

## Lead/Rhythm draft behavior

Shared-timeline Lead and Rhythm chart generation applies current reviewed positions before converting source events to `GuitarAuthoringChart` notes/chords.

Each `SharedGuitarDraftManifest` records the current reviewed-position-layer SHA-256. Any later position decision makes the existing draft stale. A stale draft cannot be treated as current; regeneration is required before downstream validation/export/package state can be trusted.

Rebuilding a guitar draft continues to invalidate validation, XML export, DLC Builder staging, and returned PSARC registration state.

## Bass scope

Bass decisions are stored and displayed through the same generic reviewed-position layer so the desktop review model remains three-arrangement-first. The existing Bass authoring path is still structurally different from the shared guitar chart path; routing reviewed Bass score positions into its final authoring artifact remains a later arrangement-editing step. Until then, Bass export safety gates remain unchanged and no reviewed Bass position is silently promoted into package authority.

## Safety boundaries

- registered score bytes remain immutable;
- fan-out JSON remains immutable;
- no position is inferred or invented by this layer;
- only an explicit human action writes a reviewed decision;
- pitch-inconsistent positions are rejected;
- stale score/fan-out/event identities fail closed;
- accepting a position does not bypass any other human review gate;
- no live Rocksmith installation or NoCableLauncher files are modified;
- no commercial/private media or Ubisoft-derived content is committed.
