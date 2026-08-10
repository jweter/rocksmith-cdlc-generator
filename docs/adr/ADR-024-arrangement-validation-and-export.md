# ADR-024: Arrangement-aware guitar validation and export

## Context

Lead and Rhythm Rocksmith XML serialization now exists, but the project still exposes only the Bass validation/export workflow through the CLI. Guitar charts also have a different trust boundary from Bass: structured sources may contain valid polyphony and exact tablature positions, but they may remain unverified, may contain unresolved MIDI-only positions, and may carry techniques the current XML bridge cannot encode losslessly.

A guitar arrangement must therefore have its own validation artifacts before it can be exported or later added to a multi-arrangement DLC Builder project.

## Decision

Add arrangement-specific Lead/Rhythm validation without changing the existing Bass validation contract.

The guitar gate validates:

- analyzed beat-map presence and bounds;
- six-string tuning presence;
- arrangement identity;
- non-empty playable chart content;
- string/fret-to-MIDI consistency;
- note and chord time bounds;
- deterministic chord-id/shape consistency;
- unresolved string/fret positions as hard failures;
- source/alignment review flags as warnings;
- unsupported imported technique semantics as warnings.

Write separate review artifacts:

- `review/lead_validation_report.json` / `review/rhythm_validation_report.json`;
- arrangement-specific flags JSON;
- arrangement-specific Markdown summaries.

Expose the workflow through:

- `cdlc build-guitar-chart PROJECT --source ... --instrument lead|rhythm`;
- `cdlc validate PROJECT --instrument bass|lead|rhythm`;
- `cdlc export PROJECT --instrument bass|lead|rhythm`.

Lead/Rhythm export writes arrangement-specific XML, provenance manifest, README, and validation evidence beneath the existing project directories.

## Alternatives

### Replace the Bass validation model with a single generalized validator immediately

Rejected for this milestone. Bass validation is already used by packaging and build staging. Replacing it wholesale would increase regression risk before multi-arrangement packaging is ready.

### Allow export with unresolved guitar positions and leave correction to EOF/DLC Builder

Rejected. The project principle is confidence-aware automation. Missing physical positions must remain explicit review failures rather than silently entering package inputs.

### Treat all unverified symbolic notes as hard failures

Rejected. Structurally valid positioned tab may still be useful as an authoring draft. It remains a visible warning until verified or user-confirmed, while unresolved or physically inconsistent positions are failures.

## Consequences

- Bass behavior remains backward-compatible.
- Lead/Rhythm now have an executable CLI path from imported/aligned notation to validation-gated Rocksmith XML.
- Multi-arrangement DLC Builder generation can consume explicit per-arrangement validation evidence in the next milestone.
- MIDI/unpositioned guitar notation remains blocked until a guitar position mapper is implemented.
