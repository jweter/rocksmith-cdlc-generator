# ADR-012: MusicXML import uses the neutral symbolic-source contract

## Status

Accepted.

## Context

Milestone 8.5 needs notation interchange from tools that can export MusicXML. MusicXML can carry pitches, rhythm, tempo/time signatures, part identity, tablature string/fret data, and staff tuning, but documents may also contain repeats, navigation directives, grace-note semantics, and other constructs whose playback timing cannot be safely guessed.

## Decision

Implement a standard-library MusicXML adapter that supports `score-partwise` `.musicxml`/`.xml` documents and compressed `.mxl` containers. Convert imported events into the existing versioned `ImportedSource` model rather than introducing MusicXML-specific downstream state.

Automatic Bass-part selection must be conservative. Ambiguity requires an explicit part index. Exact import remains `symbolic_unverified` until later alignment/reconciliation against audio evidence.

Preserve tablature string/fret and staff tuning when explicitly encoded. Preserve selected technique/tie annotations. Repeat/navigation constructs are not expanded in this phase; the importer emits warnings so playback order can be resolved by the alignment stage. Grace notes without explicit playback duration are not assigned fabricated durations.

MusicXML documents with no explicit tempo use a clearly warned temporary 120 BPM source-time assumption solely so events can enter the neutral seconds-based contract; audio alignment is responsible for correcting that assumption.

## Consequences

MusicXML becomes the third symbolic input path after MIDI and Guitar Pro while sharing the same downstream alignment/reconciliation architecture. No new runtime dependency is required. More sophisticated repeat expansion and MusicXML edge cases remain isolated from Rocksmith export logic.
