# ADR-021: Six-string guitar authoring chart and chord reconstruction

## Status

Accepted.

## Context

Lead and Rhythm structured-source import now preserves six-string tuning, string/fret positions, timing, techniques, and simultaneous notes. The Bass mapping model is intentionally monophonic and four-string-specific, so reusing it for guitar would either discard chord structure or contaminate the proven Bass path with incompatible assumptions.

## Decision

Introduce a separate `GuitarAuthoringChart` for Lead and Rhythm.

The chart:

- requires an explicit six-string tuning;
- is built from one imported Lead or Rhythm track plus the matching symbolic-to-audio alignment report;
- maps source note start/end times through the existing piecewise-linear alignment;
- preserves exact source string/fret positions only when they reproduce the source MIDI pitch under the selected tuning;
- groups notes whose aligned onsets fall within a 1 ms grouping window;
- emits one note as a single-note event and two or more distinct strings as a chord event;
- rejects duplicate-string simultaneous groups into the unresolved review queue rather than guessing;
- assigns deterministic chord IDs from sorted unique six-string fret shapes;
- keeps per-note techniques and trust class within chord events;
- marks unverified symbolic notes as review-required;
- preserves notes without usable string/fret information as unresolved rather than dropping them.

A chord shape is a six-element low-string-first fret tuple. `-1` denotes an unused string. Chord IDs are indexes into the lexicographically sorted set of unique shapes, making them deterministic for identical input.

## Consequences

Guitar Pro and tablature-bearing MusicXML can feed Lead/Rhythm authoring directly after alignment. Standard MIDI remains useful for pitch/timing evidence but cannot become exportable Rocksmith guitar events until a later guitar-position mapper resolves string/fret choices.

Rocksmith XML chord templates, chordNotes, handShapes, route masks, and DLC Builder arrangement identities are deliberately handled in the next serialization layer. This ADR does not claim that a valid internal chord is automatically valid Rocksmith XML.

## Trust boundary

The chart never upgrades `symbolic_unverified` data merely because a playable string/fret position exists. Alignment and positional validity are necessary structural evidence, not proof that the source transcription matches the recording.
