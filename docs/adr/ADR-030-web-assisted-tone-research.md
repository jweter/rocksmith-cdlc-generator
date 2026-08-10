# ADR-030: Web-assisted tone research

## Status

Accepted for implementation.

## Context

A Rocksmith arrangement is more convincing when its tone approximates the recording rather than using a generic clean or distorted preset. Mastered audio alone often cannot identify the exact historical guitar, amplifier, cabinet, pedal, rack processor, plugin, microphone, or studio chain. Multiple rigs can produce similar recorded spectra, and mixing/mastering further obscures the original signal chain.

Public gear databases and direct interviews can provide stronger constraints. Equipboard requires artist-gear submissions to include a source/proof link and explanatory context, and supports album-context tagging. Direct artist, producer, engineer, studio, and rig-rundown sources can be even stronger when they explicitly identify equipment or recording usage.

## Decision

Tone reconstruction will use a hybrid evidence pipeline:

1. Identify artist, track, album, and approximate recording era.
2. Generate targeted research queries for track-specific, album-specific, direct-interview, producer/studio, Rig Rundown, and Equipboard evidence.
3. Store every accepted claim with URL, evidence kind, scope, explanatory basis, arrangement role, and confidence.
4. Rank evidence by both source authority and specificity. Track-specific direct artist/producer evidence outranks album, era, and generic artist-level claims.
5. Accumulate independent corroboration rather than replacing one source with another.
6. Surface close contradictory candidates for human/audio review instead of silently choosing one.
7. Feed the candidate rig into a later audio-analysis stage that determines which documented effect families and tone changes are actually audible in each section.
8. Map the resulting evidence-backed tone hypothesis to the closest Rocksmith-compatible tone components.

## Evidence policy

Default authority order:

- direct artist or producer statement;
- detailed studio/session feature;
- documented rig rundown by artist/tech;
- manufacturer artist page with explicit usage context;
- source-backed Equipboard entry;
- reputable secondary reporting;
- community speculation.

Specificity modifies authority: track evidence outranks album evidence, which outranks era evidence, which outranks generic artist-level evidence.

Equipboard is treated as an evidence index, not automatically as primary truth. When its submission links to a direct interview, video, photo, or session source, the underlying source should be preserved whenever possible.

## Non-goals

- Do not claim the exact historical signal chain from audio alone.
- Do not scrape websites in ways that depend on undocumented page structure or violate source access rules.
- Do not treat artist ownership of a piece of gear as proof it was used on a specific song.
- Do not automatically install or alter Rocksmith files based on a tone hypothesis.

## Future work

- audio classifiers for gain/tone family and effect-family presence;
- delay/reverb/modulation parameter estimation;
- section-level tone-change detection;
- Rocksmith tone-component catalog and nearest-match mapping;
- benchmark metrics for effect-family precision/recall and human-rated tone similarity;
- optional web-search provider integration that converts retrieved sources into reviewable `ToneEvidence` drafts.
