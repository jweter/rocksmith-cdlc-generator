# ADR-050 — Tone listening acknowledgement

## Context

The tone-review pipeline can now bind a final inspection acknowledgement to one exact staged-settings diff before explicit final approval. The planned Live Tone Test adds another human decision: whether the proposed tone actually sounds acceptable when auditioned through a local instrument/DSP path or private dry-DI replay.

That subjective listening decision must not silently become approval, and it must become stale whenever the staged settings change.

## Decision

Add a separate `ToneListeningAcknowledgement` artifact bound to:

- artist and title;
- bound-plan SHA-256;
- tone-catalog SHA-256;
- deterministic staged-settings-diff SHA-256;
- reviewer identity;
- audition method;
- explicitly covered arrangement roles;
- one human decision: `rejected`, `keep_editing`, or `continue_to_review`.

The artifact always remains non-approving and non-injecting. Verification can optionally require `continue_to_review` when a later gate wants proof that listening did not result in rejection or continued editing.

Changing the staged-settings diff invalidates the listening acknowledgement and requires a fresh audition/review record.

## Audition methods

The first provenance vocabulary is deliberately small:

- `live_instrument` — reviewer played guitar/bass through the local audition path;
- `private_di_replay` — reviewer listened to a private dry-DI capture through the candidate chain;
- `external_preview` — reviewer used another explicit local preview route while the realtime audition engine is not yet available.

This records how the decision was reached without pretending that the current code implements realtime DSP.

## Consequences

- The future Song Workspace can write the same artifact after a Live Tone Test.
- A rejected or keep-editing audition can never satisfy a later listening prerequisite for final approval.
- Listening and approval remain separate human actions.
- No background recording, device access, DSP emulation, package generation, or Rocksmith-install modification is introduced by this slice.
- Private DI/audio remains ignored private data and is never required in CI.
