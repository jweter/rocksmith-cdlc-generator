# ADR-050: Bind human tone audition to the exact staged settings diff

## Status
Accepted

## Context

Tone settings are subjective. The project now has evidence, proposals, staging, staged-vs-original diffs, final review acknowledgement, and guarded approval. The planned Live Tone Test adds a separate human listening step using a local audio interface such as the Scarlett 2i2 or private dry-DI playback.

A listening decision must not become implicit approval, and it must become stale if the staged tone settings change after audition.

## Decision

Introduce a separate `ToneAuditionAcknowledgement` artifact that records:

- song, catalog, and bound-plan identity;
- SHA-256 of the exact normalized staged-settings diff;
- reviewer identity;
- explicit listening result: `sounds_right` or `needs_revision`;
- a human-readable description of how the tone was auditioned;
- optional reviewer note;
- `human_listening_confirmed=true`;
- `can_approve=false` and `can_inject=false`.

Verification fails closed when the current staged diff no longer matches the acknowledged digest.

The acknowledgement does not access audio hardware itself. Hardware I/O, Scarlett 2i2 qualification, approximate DSP, and private dry-DI replay remain later Live Tone Test slices. This contract lets those future surfaces produce auditable listening provenance without weakening the approval boundary.

## Safety consequences

- Listening never automatically approves a component or tone.
- A changed staged diff requires a fresh audition acknowledgement.
- No live Rocksmith installation files are read or written.
- No commercial audio, DLC, Ubisoft DSP, or private DI recordings are committed.
- Generated acknowledgement artifacts belong under ignored private storage.
