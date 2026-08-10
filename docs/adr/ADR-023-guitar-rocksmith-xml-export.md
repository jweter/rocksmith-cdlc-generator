# ADR-023: Lead and Rhythm Rocksmith 2014 XML export

## Status

Accepted.

## Context

The project now has a six-string `GuitarAuthoringChart` that preserves explicit string/fret positions, grouped chord events, per-note techniques, trust classes, and unresolved-note review state. The next boundary is serialization into Rocksmith 2014 arrangement XML without weakening the confidence-aware authoring contract.

Bass already has a minimal schema-version-7 Rocksmith XML exporter. Guitar requires additional semantics:

- `Lead` or `Rhythm` arrangement identity;
- six-string tuning offsets relative to E standard;
- `pathLead` / `pathRhythm` arrangement properties;
- deterministic chord templates;
- level chord events linked by `chordId`;
- nested `chordNote` elements for per-string techniques.

## Decision

Add `build_rocksmith_guitar_xml()` alongside the existing Bass exporter.

The exporter:

1. accepts only `lead` or `rhythm` `GuitarAuthoringChart` values;
2. refuses export while unresolved guitar notes remain;
3. emits tuning offsets by physical string index relative to `(40, 45, 50, 55, 59, 64)`;
4. emits one deterministic chord template for every unique `chord_id` represented in the chart;
5. uses the chart's six-string fret shape directly (`-1` for unused strings);
6. does not invent left-hand fingering and therefore writes `finger0` through `finger5` as `-1`;
7. emits nested `chordNote` data so losslessly supported per-note techniques survive chord export;
8. preserves the existing conservative direct-technique policy for palm mute, harmonic, tremolo picking, accent, and vibrato;
9. keeps the existing one-phrase, one-section, one-difficulty scaffold until phrase analysis and Dynamic Difficulty are implemented.

## Compatibility basis

Rocksmith Custom Song Toolkit supports Rocksmith 2014 custom tunings and schema-version-7 arrangement XML. Existing toolkit and Rocksmith2014.NET-compatible arrangement structures use six-string chord-template fret/finger fields, chord events referencing `chordId`, and nested chord-note information for string-level note semantics.

## Consequences

- Lead and Rhythm now have a deterministic Rocksmith XML serialization boundary.
- Alternate tunings are represented as per-string semitone offsets rather than named presets.
- Chord names and fingerings remain intentionally blank/unknown instead of being guessed.
- Unresolved MIDI/unpositioned guitar notes block XML export until a future guitar-position mapper or human review supplies valid positions.
- Packaging, generalized validation gates, hand-shape generation, phrase generation, tones, and Dynamic Difficulty remain separate milestones.
