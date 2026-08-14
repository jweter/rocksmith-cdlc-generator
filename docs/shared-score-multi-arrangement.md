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

Mapping confidence is therefore metadata, not permission to bypass review. A future importer can record why it proposed a mapping, while the GUI can present those reasons to the user.

## Shared timing

Once the complete score is aligned to the recording, Bass, Lead, and Rhythm should inherit the same score-to-recording timeline. Arrangement-specific reconciliation may still adjust notes, chords, techniques, or fingering, but the project should not independently rediscover song structure three times.

## Current boundary

`ProjectScoreSource` establishes the persistent contract for one score, its discovered tracks, and Bass/Lead/Rhythm mappings. Existing per-arrangement importers continue to work while later changes teach Guitar Pro and MusicXML adapters to populate this contract directly and fan the selected tracks into arrangement-specific imported sources.

Rights/provenance remain source-level and human reviewed. Musical correctness, ambiguous track mapping, reconciliation, fingering, validation findings, and final packaging remain separate review concerns.
