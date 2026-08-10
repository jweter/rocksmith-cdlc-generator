# Source Import & Reconciliation Plan

## Goal

Make credible symbolic sources a first-class input so the generator can use audio analysis as verification/alignment rather than forcing every song through uncertain transcription.

## Architecture

```text
local audio ───────────────┐
clean stem ────────────────┤
GP3/GP4/GP5 ───────────────┤
MusicXML ──────────────────┤→ canonical source events → alignment/reconciliation → canonical arrangement
MIDI ──────────────────────┤                                  ↑
selected custom PSARC ─────┘                                  │
                                               audio-derived evidence
```

Every imported or generated event must retain provenance and confidence. Reconciliation must create explicit disagreements rather than silently overwriting one source with another.

## Phase 1 — Neutral import contract

Create versioned source-event models that can represent:
- instrument/track identity;
- MIDI pitch and optional note spelling;
- onset/duration in source time;
- optional string/fret;
- optional technique annotations;
- source tempo/time-signature information;
- source filename/type/hash;
- importer/version;
- confidence/trust class;
- review flags.

The import contract must not contain EOF- or DLC Builder-specific fields.

## Phase 2 — MIDI importer

Implement MIDI first because the repository already produces MIDI and it gives us a simple round-trip target.

Acceptance tests:
- preserve pitch and duration;
- choose requested Bass track deterministically;
- handle tempo maps;
- reject malformed/ambiguous files clearly;
- preserve source SHA/provenance.

## Phase 3 — Guitar Pro importer

Initial target: `.gp3`, `.gp4`, `.gp5` through an adapter around an established parser such as PyGuitarPro.

Requirements:
- import Bass/Guitar tracks independently;
- preserve explicit string/fret fingering where present;
- preserve tuning;
- preserve techniques as annotations but do not automatically trust/export every technique;
- convert timing into neutral source-time events;
- keep parser dependency optional from the core runtime.

Newer formats should be handled through a separate adapter/conversion path rather than pretending old-format parsers support them.

## Phase 4 — MusicXML importer

Use MusicXML as the neutral interchange route for notation applications.

Requirements:
- part/instrument selection;
- pitch, duration, rests, ties, tempo/time-signature import;
- tablature/string/fret import where actually encoded;
- deterministic handling of pickup measures and repeats, with unsupported constructs flagged.

## Phase 5 — Existing custom Rocksmith import

Allow only a file explicitly selected by the user. Do not scan or modify the live Rocksmith DLC directory.

Use Rocksmith2014.NET-compatible tooling to recover arrangement/chart information rather than reimplementing PSARC/SNG internals unless a narrowly scoped parser is later justified.

Imported official/custom content remains source material for the user's local project; the application must not redistribute the underlying package or chart.

## Phase 6 — Metadata identification

Add a metadata-provider interface.

First candidate: MusicBrainz for recording/release/artist/album/year identification. Metadata lookup should be advisory and reviewable; never overwrite explicit user metadata silently.

Proposed flow:
```text
cdlc identify PROJECT
→ ranked candidates
→ user/automation chooses high-confidence match
→ project metadata records provider IDs and provenance
```

## Phase 7 — Licensed/public-domain audio providers

Add a provider abstraction rather than coupling the project to one website.

Provider requirements:
- explicit evidence that the track is downloadable under the provider's terms;
- record source URL/provider/license metadata;
- hash downloaded audio immediately;
- normalize through the same immutable ingest path as local files.

Jamendo is a candidate for Creative-Commons/end-to-end fixtures. Public-domain/original fixtures remain preferred for CI.

Do not build stream-ripping paths for Spotify, Apple Music, YouTube, or similar services. Do not scrape or bypass paid tab-download functionality.

## Phase 8 — Alignment

Imported notation usually does not line up perfectly with the recording. Build an alignment layer before reconciliation.

Inputs:
- notation tempo map/note onsets;
- analyzed audio beat grid;
- optional onset/pitch evidence.

Outputs:
```text
analysis/alignment.json
```

Include:
- global offset;
- piecewise time-warp anchors;
- alignment error statistics;
- confidence per region;
- flagged regions where alignment is unreliable.

Start with beat/measure alignment and monotonic piecewise interpolation. Do not use unconstrained warping that can reorder musical events.

## Phase 9 — Source reconciliation

For every candidate note, compare:
- imported symbolic pitch;
- imported rhythm;
- imported string/fret/tuning;
- audio transcription pitch/timing/confidence;
- playable fretboard constraints.

Suggested trust behavior:
- high-confidence symbolic + supporting audio: accept with high confidence;
- high-confidence symbolic + weak audio: retain symbolic source, flag only if necessary;
- symbolic/audio disagreement: preserve both candidates and create a review item;
- no symbolic fingering: run sequence fret mapper;
- symbolic fingering impossible under selected tuning: FAIL/review rather than silently remap.

Outputs:
```text
charts/bass_reconciled.json
review/source_disagreements.json
```

## Phase 10 — Product workflow

Target user flow:

```text
1. Add local/licensed audio
2. Identify metadata
3. Add optional GP/MIDI/MusicXML/custom PSARC
4. Analyze beats
5. Import + align symbolic source
6. Run audio transcription as verification/fallback
7. Reconcile sources
8. Review disagreements/low-confidence regions
9. Map missing fingering
10. Validate → authoring export → DLC Builder → staged PSARC
```

## Metrics

Measure for audio-only and symbolic-assisted workflows:
- pitch precision/recall on legal ground-truth fixtures;
- median onset error;
- alignment residual error;
- disagreement count per song minute;
- review flags per song minute;
- human editing minutes per finished song minute.

The source-import feature is successful only if it measurably reduces correction time without hiding disagreements.