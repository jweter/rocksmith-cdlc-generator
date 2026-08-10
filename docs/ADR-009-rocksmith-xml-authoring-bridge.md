# ADR-009: Rocksmith 2014 XML authoring bridge

Status: Accepted for Milestone 7 MVP

## Context

The generator's canonical timing, transcription, and fret/string mapping formats are intentionally independent from EOF and DLC Builder. Milestone 7 needs a deterministic interchange artifact that established Rocksmith authoring tools can consume without making `.psarc` packaging part of the Python core.

The Rocksmith2014.NET repository contains integration fixtures produced by EOF for Rocksmith 2014 instrumental arrangements. The Bass fixture uses `<song version="7">`, `<ebeats>`, semitone-offset `<tuning>`, phrase/section metadata, time-signature events, and `<levels>` containing mapped `<note time/string/fret/sustain>` events. Rocksmith2014.NET also contains XML-to-SNG and DLC Builder processing code around this arrangement format.

## Decision

Milestone 7 exports a validation-gated Rocksmith 2014 Bass arrangement XML to `eof/arr_bass_RS2.xml`.

The exporter:

- consumes canonical `analysis/tempo_map.json` and `charts/bass_mapped.json`;
- refuses export while unified validation is `FAIL`;
- emits Rocksmith song XML schema version 7;
- converts absolute bass open-string MIDI pitches to Rocksmith semitone tuning offsets relative to E1/A1/D2/G2;
- preserves analyzed beat timestamps and time signature;
- exports one difficulty level containing mapped bass notes;
- represents note duration as Rocksmith `sustain`;
- emits one full-song phrase and section until section analysis is implemented;
- emits no techniques, chords, anchors, tones, or Dynamic Difficulty that were not derived by upstream stages;
- writes `eof/export_manifest.json` documenting provenance and limitations.

The Python project does not reimplement SNG or PSARC creation in this milestone.

## Rationale

This creates a narrow compatibility boundary while keeping the canonical project representation tool-independent. It also preserves the roadmap's human-review-first architecture: generated XML is an authoring handoff, not a claim that the arrangement is finished.

Generating only supported information is safer than filling mandatory-looking fields with guesses. Established Rocksmith tooling can add downstream authoring metadata, Dynamic Difficulty, tones, and packaging after review.

## Consequences

- The first XML is intentionally sparse compared with a polished EOF arrangement.
- Section analysis is still needed for musically meaningful phrase/section structure.
- Technique inference and anchor generation remain separate future work.
- DLC Builder automation can be built as a later bridge without changing the canonical chart model.
- Compatibility tests should continue to compare our XML structure against Rocksmith2014.NET fixtures and, eventually, parse the generated XML through Rocksmith2014.NET itself in an integration test.
