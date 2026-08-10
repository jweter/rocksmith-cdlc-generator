# ADR-011: Neutral Symbolic Source Contract and MIDI Import

## Status

Accepted for Milestone 8.5 Phase 1/2.

## Context

The generator must ingest symbolic sources such as MIDI, Guitar Pro, MusicXML, and selected custom Rocksmith arrangements without coupling those inputs to EOF or DLC Builder schemas. Imported data also needs to remain distinguishable from audio-derived evidence so later reconciliation can expose disagreements instead of silently overwriting one source with another.

## Decision

All symbolic importers target a versioned `ImportedSource` model containing source provenance, source tempo/time-signature events, track identity, note timing/pitch, optional string/fret/tuning, optional technique annotations, import confidence, trust class, and review flags.

`import_confidence` represents fidelity of decoding the source file, not confidence that the source matches the recording. MIDI events decoded without ambiguity therefore receive import confidence 1.0 but remain `symbolic_unverified` until alignment/reconciliation.

The first importer supports Standard MIDI Files through Mido. Bass track selection is deterministic when one candidate is clearly identified by track/instrument name, General MIDI bass program, or pitch range. Ambiguous files require an explicit track index rather than guessing.

MIDI tempo changes are converted into absolute seconds using the complete file tempo map. Malformed note-on/note-off pairs are rejected rather than repaired silently.

Imported artifacts are written below `sources/imported/` and retain source filename and SHA-256. The source file itself is not redistributed or copied automatically by this importer.

## Consequences

- Guitar Pro, MusicXML, and PSARC adapters can share one neutral output contract.
- Alignment can operate on source-time events independent of the source format.
- Reconciliation can distinguish exact import fidelity from musical verification against audio.
- Ambiguous track selection becomes an explicit user/review decision.
- No EOF/DLC Builder fields leak into the source-import model.
