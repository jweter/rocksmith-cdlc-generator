# Shared score, multi-arrangement architecture

## Product target

The intended authoring path is one local recording plus one complete symbolic score, producing independent Rocksmith Bass, Lead, and Rhythm arrangements from a shared musical source.

The score is a project-level source. It must not be ingested three separate times merely because three Rocksmith arrangements consume it.

## Project shape

A project may contain:

- one immutable local recording;
- one complete Guitar Pro, GPIF, MusicXML/MXL, or MIDI score source;
- a score-track inventory;
- zero or one mapping from a score track/part to each Rocksmith role: `bass`, `lead`, and `rhythm`;
- one shared recording/score synchronization model;
- independent downstream arrangement state, validation, and human review for Bass, Lead, and Rhythm.

## Track mapping

Track names and instrument metadata may propose mappings such as:

- `Bass` -> Bass;
- `Lead Guitar` or `Solo Guitar` -> Lead;
- `Rhythm Guitar` or chord-oriented guitar -> Rhythm.

A proposal is not the same as human confirmation. Ambiguous files must preserve candidate tracks and stop for explicit review rather than silently choosing an arrangement.

Mapping confidence is evidence for review, not permission to bypass it. Even a proposal with confidence `1.0` remains human-review-required until a person explicitly confirms the Bass, Lead, or Rhythm assignment. This keeps importer certainty separate from source acceptance and gives the future GUI one consistent confirmation boundary.

## Confirmed arrangement fan-out

`cdlc-score-fanout PROJECT` is the deterministic bridge from the shared score contract into arrangement-specific normalized sources. It consumes only mappings with `human_confirmed=true`, uses the immutable score copy already stored inside the project, and requires score rights/provenance to no longer be review-pending.

The command can fan out every confirmed role or restrict work with repeated `--role bass|lead|rhythm` arguments. Guitar Pro 3-5 and MusicXML/MXL use their existing explicit-track importers, so the confirmed track index is passed directly rather than re-running automatic role selection.

A project-level `score-fanout-<sha>.json` manifest is published only after every requested output validates against the registered score SHA-256, selected track index, and arrangement role. A stale manifest is removed before fallible re-import begins, so partial outputs left by a failed run are never presented as a coherent authoritative arrangement set.

Mapping confirmation and fan-out share the same project score transaction lock. A mapping cannot change while fan-out is importing, validating, and publishing its authority manifest, and concurrent fan-out runs are serialized. On Windows the transaction lock retries lock contention until the active transaction completes rather than failing after the finite `msvcrt.LK_LOCK` retry window; non-contention acquisition failures surface directly, and cleanup only releases a lock that was actually acquired. If a human actually changes a confirmed mapping after a successful fan-out, that confirmation invalidates the existing fan-out manifest before updating the mapping contract. Repeating an already-confirmed role-to-track choice is a true no-op and preserves the still-valid fan-out manifest.

When fan-out makes a Bass score track authoritative, Bass-derived reconciliation, mapped-chart, disagreement-review, and validation artifacts are preserved only when the existing reconciliation is explicitly bound to the same score SHA-256 and Bass track index. Otherwise those downstream artifacts are invalidated before the new fan-out manifest is published, preventing a superseded legacy Bass chart from silently flowing through automatic mapping and validation.

Fan-out does not make the resulting notes trusted musical ground truth. Alignment, reconciliation, fingering, tone, validation findings, and final packaging remain later independent gates.

## Shared timing

Once the complete score is aligned to the recording, Bass, Lead, and Rhythm should inherit the same score-to-recording timeline. Arrangement-specific reconciliation may still adjust notes, chords, techniques, or fingering, but the project should not independently rediscover song structure three times.

## Workflow planner handoff

When a current fan-out manifest contains a human-confirmed Bass arrangement, the workflow planner treats that output as the authoritative Bass symbolic source for the next alignment step. It does not ask the user to choose again among older imported Bass files, because that source decision was already made explicitly through score-track confirmation. If the current fan-out has only Lead and/or Rhythm, legacy Bass inputs remain available and are not suppressed.

This is the first downstream consumer of the project-level fan-out authority. It preserves the existing Bass alignment/reconciliation implementation while moving source selection onto the shared score contract. The next timing slice should promote the resulting score-to-recording alignment into shared project timing state that Lead and Rhythm can inherit rather than aligning each arrangement independently.

## Current boundary

`ProjectScoreSource` establishes the persistent contract for one score, its discovered tracks, and Bass/Lead/Rhythm mappings. Confirmed Guitar Pro 3-5 and MusicXML/MXL mappings can fan out into arrangement-specific normalized source JSON from that single registered score snapshot, and workflow planning now consumes the authoritative Bass fan-out output for alignment when one exists.

Rights/provenance remain source-level and human reviewed. Musical correctness, track mapping, reconciliation, fingering, validation findings, and final packaging remain separate review concerns.
