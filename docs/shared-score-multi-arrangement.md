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

Mapping confirmation and fan-out share the same project score transaction lock. A mapping cannot change while fan-out is importing, validating, and publishing its authority manifest, and concurrent fan-out runs are serialized. If a human changes a confirmed mapping after a successful fan-out, that confirmation invalidates the existing fan-out manifest before updating the mapping contract, so stale arrangement authority cannot survive a remap.

Fan-out does not make the resulting notes trusted musical ground truth. Alignment, reconciliation, fingering, tone, validation findings, and final packaging remain later independent gates.

## Shared timing

Once the complete score is aligned to the recording, Bass, Lead, and Rhythm should inherit the same score-to-recording timeline. Arrangement-specific reconciliation may still adjust notes, chords, techniques, or fingering, but the project should not independently rediscover song structure three times.

## Current boundary

`ProjectScoreSource` establishes the persistent contract for one score, its discovered tracks, and Bass/Lead/Rhythm mappings. Confirmed Guitar Pro 3-5 and MusicXML/MXL mappings can now fan out into arrangement-specific normalized source JSON from that single registered score snapshot.

The next architectural step is to make workflow planning/alignment consume this project-level fan-out manifest and shared timing state instead of treating Bass as the only automated arrangement path.

Rights/provenance remain source-level and human reviewed. Musical correctness, track mapping, reconciliation, fingering, validation findings, and final packaging remain separate review concerns.
