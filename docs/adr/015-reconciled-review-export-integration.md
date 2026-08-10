# ADR-015: Reconciled review and Rocksmith export integration

## Status

Accepted

## Context

Milestone 8.5 can now import MIDI, Guitar Pro, and MusicXML, align symbolic timing to the recording, reconcile symbolic notes with audio transcription, and preserve valid symbolic Bass fingering through mapping. The remaining integration risk is allowing these richer artifacts to bypass the existing validation/review gate or silently dropping imported performance techniques during Rocksmith XML export.

## Decision

1. `cdlc map-bass` exposes `--source auto|raw|reconciled`.
2. `auto` remains the default and prefers `charts/bass_reconciled.json` when it exists; `raw` preserves the original audio-only workflow.
3. `review/source_disagreements.json`, when present, is incorporated into the unified validation review queue. Reconciliation disagreements are warnings, not automatic packaging failures, because they are explicit human-review items rather than structural corruption.
4. A malformed disagreement artifact is a validation failure because its review state cannot be trusted.
5. Imported techniques are only encoded into Rocksmith XML when the current neutral representation contains enough information to do so losslessly.
6. Directly supported technique labels are `palm_mute`, `harmonic`, `tremolo_picking`, `vibrato`, `accent`, and `heavy_accent`.
7. Generic hammer-on/pull-off, slide, bend, grace, trill, tie, staccato, let-ring, ghost-note, and other techniques that need direction, target, curve, or additional semantics remain review warnings rather than fabricated Rocksmith attributes.
8. Rocksmith arrangement properties reflect supported techniques actually emitted by the mapped chart.

## Consequences

- The symbolic/audio workflow now reaches the same validation and export path as audio-only generation.
- Good Guitar Pro or MusicXML fingering and directly representable techniques survive through Rocksmith XML.
- Unsupported technique information is visible in the review queue rather than silently lost.
- Packaging remains allowed with warnings so a human can explicitly review and accept unresolved musical details.
- Future technique work can expand the neutral source model with slide targets, bend curves, HOPO direction, and other data without breaking this contract.
