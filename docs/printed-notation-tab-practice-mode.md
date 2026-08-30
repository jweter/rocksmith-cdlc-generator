# Printed Notation / TAB Practice Mode

Status: planned roadmap capability

This document defines a new Rocksmith CDLC Generator input and practice workflow: create a playable Rocksmith 2014 arrangement from photographed or scanned printed music notation / tablature, even when no commercial backing recording is used.

The intended user workflow is simple:

```text
Photograph or scan a notation / TAB page
        ↓
Import image(s) into the Windows app
        ↓
Recognize notation + tablature
        ↓
Reconstruct measures, beats, rests, note durations, strings/frets, chords, repeats and techniques
        ↓
Human review of uncertain recognition
        ↓
Generate deterministic tempo map
        ↓
Generate practice audio (count-in + click + optional simple backing accompaniment)
        ↓
Generate Rocksmith Bass / Lead / Rhythm arrangement(s)
        ↓
Validate
        ↓
DLC Builder / PSARC handoff
```

The critical product idea is that the printed score becomes the primary musical source. The system does not need a commercial recording merely to provide Rocksmith timing. The generated chart, click track, and generated backing accompaniment all use the same authoritative tempo/measure map, so they remain synchronized by construction.

## Product goals

1. Allow a user to take a clear photograph or scan of legally owned notation / TAB and turn it into a playable Rocksmith practice arrangement.
2. Preserve exact string/fret choices from tablature whenever the source contains them instead of re-inferring fretboard positions from pitch.
3. Preserve rhythmic notation, rests, ties, dotted values, tuplets, repeat structures, alternate endings, tempo markings, time signatures and measure boundaries as structured data.
4. Generate useful timing audio without requiring a copyrighted backing track.
5. Make rhythm practice a first-class feature through audible count-ins, accented downbeats, metronome clicks, optional subdivisions, looping and tempo scaling.
6. Optionally generate simple backing accompaniment derived from the score so practice feels musical rather than like a silent note highway.
7. Keep recognition confidence and provenance explicit. Ambiguous printed symbols must enter review instead of silently becoming authoritative chart content.
8. Reuse the existing canonical arrangement, validation, review, Rocksmith XML and package pipeline after notation recognition has produced structured events.

## Supported source material

Initial target material:

- professionally printed bass TAB + standard notation;
- professionally printed guitar TAB + standard notation;
- clear photographs from a phone camera;
- flatbed or document scans;
- one page at a time initially, expanding to multi-page songs;
- standard 4-, 5-, and 6-string bass where representable;
- 6-string guitar;
- Bass, Lead and Rhythm arrangements.

Later adapters may support notation-only pages without TAB, handwritten material, chord charts, drum-style rhythmic cues, or mixed-reference pages, but those are not required for the first implementation.

## Why TAB is especially valuable

Printed TAB already contains Rocksmith-critical information that audio transcription or standard notation alone does not necessarily provide:

- string identity;
- fret number;
- chord voicing;
- physical position choice;
- repeated-note string choice;
- many slides / hammer-ons / pull-offs / bends and other technique markings.

When reliable TAB is present, preserve those physical choices as source evidence rather than solving pitch-to-fret mapping again. Standard notation remains useful as a cross-check for pitch, rhythm, key, accidentals and voice structure.

## Recognition architecture

Do not use one unconstrained general-purpose vision model as the sole authority for an entire book page.

Use a staged recognition and verification pipeline:

```text
Page image
  ↓
Image normalization / deskew / crop / perspective correction
  ↓
Staff + TAB-line detection
  ↓
Measure / barline segmentation
  ↓
Symbol and fret-number recognition
  ↓
Optical Music Recognition / notation parsing
  ↓
TAB-to-notation cross-check
  ↓
Deterministic measure reconstruction
  ↓
Confidence scoring + ambiguity detection
  ↓
Vision/AI assistance only for ambiguous regions where useful
  ↓
Human review queue
  ↓
Promoted structured score
```

The source page image is evidence. Parsed events are derived data. Human-approved corrections become review authority. Downstream generated Rocksmith events must be invalidated if the source page identity or promoted recognition changes.

## Image preprocessing

Phone photographs will not always be square to the page. The importer should support:

- page boundary detection;
- perspective correction;
- rotation / deskew;
- contrast normalization;
- glare / shadow warnings;
- blur detection;
- resolution sufficiency checks;
- cropping to a page or selected system;
- multi-page ordering.

The UI should tell the user when a better photograph is preferable to attempting low-confidence recognition.

## Canonical recognized event data

Recognition should produce the same tool-independent canonical musical model used by the rest of the generator.

Each event should preserve provenance and confidence, for example:

```json
{
  "measure": 37,
  "beat": 2.5,
  "duration_beats": 0.5,
  "pitch": 43,
  "string": 0,
  "fret": 3,
  "techniques": [],
  "source": {
    "kind": "printed_tab_image",
    "page": 12,
    "region": [412, 1160, 498, 1240]
  },
  "confidence": {
    "fret": 0.997,
    "rhythm": 0.964,
    "technique": 0.81
  },
  "review_required": true
}
```

The representation must also support rests and structural events. A rest is not the absence of data; it is explicit musical timing evidence and is important for preventing false sustains or notes in intentionally silent regions.

## Recognition review queue

Review should be targeted rather than forcing manual re-entry of the page.

Examples:

```text
Page 12 / Measure 37
Possible fret digit: 3 vs 8
Confidence: 0.61
Action: choose 3 or 8

Page 12 / Measure 38
Possible slide marking: 5→7
Confidence: 0.73
Action: confirm technique

Page 13 / Measure 41
Rhythm total is 3.5 beats in a 4/4 measure
Action: inspect missing rest / dot / tie / tuplet
```

The system should automatically flag:

- impossible measure-duration totals;
- TAB and standard-notation pitch disagreement;
- fret/string combinations outside the declared instrument;
- ambiguous digits;
- ambiguous accidentals;
- unresolved ties/slurs;
- uncertain tuplets;
- repeated-measure navigation uncertainty;
- missing repeat endings;
- unknown symbols;
- likely scan/page-order gaps.

## Deterministic timing without a commercial recording

A printed-score project can create its own song clock.

Example:

```text
4/4 at 120 BPM
quarter note = 0.500 s
eighth note  = 0.250 s
16th note    = 0.125 s
one measure  = 2.000 s
```

Tempo changes become explicit tempo-map segments. All generated audio and arrangement event timestamps are derived from the same map.

If the page gives an approximate tempo such as `♩ = 120`, that value becomes the initial practice tempo. Because no commercial recording is being synchronized, internal consistency is more important than matching an external waveform.

The system should support:

- constant tempo;
- explicit metronome marks;
- time-signature changes;
- tempo changes;
- ritardando / accelerando represented conservatively and reviewed where necessary;
- pickups / anacrusis;
- fermatas where supported by the practice model;
- repeat expansion into a deterministic playback timeline.

## Click-track practice audio

Click track is a core feature, not an afterthought.

Default practice audio should provide:

- 1- or 2-measure count-in;
- distinct measure downbeat accent;
- normal beat clicks;
- optional eighth-note or sixteenth-note subdivisions;
- optional subdivision only in selected difficult measures;
- tempo changes that follow the same authoritative tempo map as the note highway;
- configurable click level relative to generated accompaniment;
- optional spoken/count-style count-in later if useful.

Because both chart and click come from the same clock, drift should be structurally impossible unless there is a bug in rendering/export. Tests should verify event-to-click agreement at measure boundaries throughout the full arrangement.

## Generated backing accompaniment

The mode should offer more than silence when desired, while remaining independent of copyrighted commercial audio.

The first version should generate deliberately simple accompaniment from the recognized score rather than attempting to recreate the original record.

Possible layers:

1. **Click only** — count-in + metronome.
2. **Click + drums** — simple synthesized kick/snare/hi-hat pattern derived from meter and beat emphasis.
3. **Click + harmonic backing** — synthesized root/chord pads or simple rhythm-guitar/piano-like chord voicings when harmonic information can be derived reliably.
4. **Click + bass/guitar guide** — synthesized guide rendering of the target notation, useful for ear-checking recognition before practice. This should be separately toggleable so the learner can mute the part they are playing.
5. **Practice band** — basic generated drums + harmonic bed + optional guide instrument, all generated from structured notation and all following the same tempo map.

Generated accompaniment is a practice aid, not an attempt to imitate or redistribute the original copyrighted recording.

The initial backing engine should favor deterministic synthesis or MIDI/soundfont-style rendering over generative audio models. Deterministic rendering is faster, reproducible, testable, and guarantees alignment. More sophisticated generated accompaniment can be evaluated later only if it materially improves practice value without introducing timing uncertainty or licensing ambiguity.

## Practice tempo modes

Every notation-derived arrangement should support tempo scaling because no commercial backing recording constrains playback speed.

Examples:

- 50% / very slow;
- 60%;
- 70%;
- 75%;
- 80%;
- 90%;
- 100% / printed tempo;
- custom BPM or percentage.

Tempo scaling should regenerate the entire practice clock deterministically rather than manually scaling individual event timestamps.

Rocksmith package strategy must be evaluated. If Rocksmith itself cannot dynamically change package tempo in the desired way, the generator may produce separate practice variants/packages from one canonical score while preserving a shared source identity.

## Measure-based looping

The natural unit for printed-score practice is the measure, not a timestamp.

The UI should allow:

```text
Loop measures 41–48
Count in: 2 measures
Tempo: 70%
Subdivision: eighth notes
Backing: drums + chords
```

The loop should:

- begin with optional count-in;
- play the selected measures;
- optionally provide a short separation cue;
- repeat without timing drift;
- preserve any local tempo/time-signature changes;
- support quick expansion by ±1 measure / phrase;
- display both measure/beat and clock time.

## Partial-song / exercise generation

A photographed page does not need to represent an entire song.

Supported targets should eventually include:

- whole song;
- one page;
- selected systems;
- selected measures;
- verse riff only;
- chorus only;
- solo only;
- bass exercise;
- lead exercise;
- rhythm exercise;
- technique drill created from score measures.

This makes the feature useful even before full multi-page song reconstruction is complete.

## Multi-page song assembly

After the single-page proof of concept works, add multi-page ingestion:

- page ordering;
- printed page-number recognition where reliable;
- repeated system headers and song-title metadata handling;
- continuity validation across page breaks;
- measure-number continuity;
- repeat/coda/segno navigation;
- first/second endings;
- missing-page detection;
- duplicate-page detection;
- overlapping photograph detection;
- source-region links so every recognized event can navigate back to the original page location.

## Arrangement mapping

Printed books may contain one or several guitar/bass parts.

The review UI should allow explicit mapping to:

- Bass;
- Lead Guitar;
- Rhythm Guitar;
- optional alternate guitar arrangement later.

If one page contains a single instrument, only that arrangement needs to be generated. A bass-only notation book should create a bass Rocksmith practice arrangement without requiring artificial Lead/Rhythm content.

For guitar books containing multiple staves/parts, preserve each source part independently until the user confirms its Rocksmith arrangement role.

## Validation

Notation-derived builds must pass both recognition validation and normal Rocksmith validation.

Additional checks include:

- every measure sums correctly after tuplets/ties/rests/repeats are resolved;
- no unexplained time gaps unless represented as rests;
- no sustain crosses an explicit rest or incompatible subsequent event;
- tab string/fret produces the expected notated pitch under declared tuning/capo;
- chords are physically valid;
- repeat expansion is deterministic;
- click downbeats match measure starts;
- accompaniment events share the same clock;
- practice tempo variants preserve musical beat positions;
- page provenance exists for every recognized event;
- unresolved low-confidence recognition blocks final promotion where it can affect correctness.

Existing EOF/Rocksmith mature-reference rules remain applicable downstream.

## UI requirements

Add a Notation / TAB import path to the Windows application.

Suggested workflow:

```text
New project
  → Source type: Recording + score | Structured score only | Printed notation/TAB
  → Add page image(s)
  → Image-quality check
  → Detect systems/measures
  → Recognition preview
  → Review flagged regions
  → Confirm instrument/tuning/capo
  → Confirm tempo/time signatures/repeats
  → Promote score
  → Configure Practice Audio
  → Generate Rocksmith arrangement
```

Recognition review should show the source image and parsed result together. Clicking a parsed note should highlight its source image region; clicking an image region should select the corresponding canonical event when available.

Practice Audio controls should expose:

- click on/off;
- count-in length;
- downbeat accent;
- subdivision mode;
- backing mode;
- target-part guide on/off;
- tempo percentage / BPM;
- selected loop measures.

## First proof of concept

The first acceptance target should be intentionally narrow:

```text
one clear photographed bass-TAB page
        ↓
4–8 consecutive measures
        ↓
recognized string/fret + rhythm + rests
        ↓
human review of any ambiguous symbols
        ↓
generated tempo map
        ↓
2-measure count-in + click track
        ↓
optional simple generated drum/harmonic backing
        ↓
Rocksmith bass arrangement
        ↓
validation
        ↓
playable practice PSARC
```

Acceptance criteria:

- all selected measures reconstruct to the correct number of beats;
- string/fret positions match the printed TAB after review;
- rests produce actual empty chart regions;
- sustains end correctly and never bridge explicit rests unless the notation explicitly ties through them;
- click remains sample/clock aligned with measure boundaries from first to last measure;
- Rocksmith note highway is synchronized with the click;
- the user can play the exercise without any original backing recording;
- a generated backing option can be enabled without altering chart timing;
- recognized events can be traced back to page regions;
- uncertain recognition is visible rather than hidden.

## Development phases

### N0 — Research and fixture definition

- identify candidate Optical Music Recognition libraries / models and their licenses;
- inspect mature open-source notation/TAB parsing implementations before inventing custom semantics;
- create synthetic/public-domain or privately held local test fixtures without committing copyrighted book pages;
- define canonical page/source provenance schema;
- define recognition confidence and promotion rules.

### N1 — Image intake

- local image registration and hashing;
- page quality diagnostics;
- perspective/rotation correction;
- crop preview;
- source immutability and stale-state invalidation.

### N2 — Single-page measure recognition

- staff/TAB line detection;
- barline/measure segmentation;
- fret-number recognition;
- rhythm/rest extraction;
- standard-notation cross-check where present;
- 4–8 measure canonical export.

### N3 — Recognition review

- source-image ↔ event navigation;
- ambiguity queue;
- corrections with provenance;
- measure-duration validator;
- explicit promotion to authoritative structured score.

### N4 — Practice clock + click

- authoritative tempo map from notation;
- count-in;
- downbeat accent;
- beat clicks;
- subdivisions;
- tempo scaling;
- full-length drift tests.

### N5 — Generated backing audio

- deterministic drum accompaniment;
- harmonic accompaniment when chord/key evidence permits;
- synthesized target guide rendering;
- per-layer mute/level settings;
- reproducible audio rendering from project configuration.

### N6 — Rocksmith practice export

- arrangement generation from promoted score;
- explicit rest/sustain correctness checks;
- XML/package handoff;
- first playable no-commercial-audio practice PSARC.

### N7 — Measure looping and exercise creation

- select measure range;
- count-in before each repetition;
- loop preview in desktop app;
- export selected-range practice package if required by Rocksmith constraints.

### N8 — Multi-page songs

- page ordering;
- continuity and missing-page checks;
- repeat/coda/alternate-ending expansion;
- complete-song assembly;
- Bass/Lead/Rhythm mapping across pages.

### N9 — Product hardening

- benchmark photographed vs scanned pages;
- quantify symbol/fret/rhythm recognition accuracy;
- measure human correction time per page;
- GUI usability testing;
- regression corpus with legal/synthetic fixtures;
- performance optimization on full songs.

## Benchmark metrics

Track separately:

- fret digit accuracy;
- string assignment accuracy;
- pitch agreement with standard notation;
- onset/beat accuracy;
- duration accuracy;
- rest accuracy;
- chord reconstruction accuracy;
- technique precision;
- measure-completeness rate;
- repeat/navigation correctness;
- low-confidence recall (did the system flag its own mistakes?);
- human corrections per measure;
- human review minutes per page;
- end-to-end editing minutes per finished minute;
- click/chart timing error at measure boundaries;
- generated-backing/chart timing error.

A recognition system that is slightly less aggressive but reliably flags ambiguity is preferable to one that guesses incorrectly with high apparent confidence.

## Copyright and repository boundary

This feature is intended for personal authoring from material the user is legally able to use. Do not commit commercial book scans or photographs into the public repository.

Repository fixtures should use:

- synthetic pages generated for tests;
- public-domain notation;
- original notation created for the project;
- tiny abstract fixtures that contain no protected song expression.

The application should keep imported commercial page images in local/private project storage and record only appropriate metadata/hashes in derived reports.

Generated accompaniment must be based on structured musical information and should not attempt to clone the protected recording or a specific performer/recording timbre.

## Relationship to existing source hierarchy

The project already prefers structured sources when available. Printed notation/TAB becomes another structured-source route after recognition and review:

```text
Source hierarchy

1. Reviewed native structured score (Guitar Pro / MusicXML / MIDI where supported)
2. Reviewed printed notation/TAB recognition
3. Isolated instrument stem
4. Full-mix audio transcription
```

The exact ordering between native structured score and printed professional TAB can be determined by provenance/quality, but both should be treated as substantially stronger note evidence than unconstrained full-mix transcription.

After promotion, downstream code should consume a common canonical score/arrangement representation and should not care whether the events originated from Guitar Pro, MusicXML, MIDI or a photographed page.

## Relationship to audio-backed song creation

This mode does not replace the existing recording + score workflow.

Two valid product paths should coexist:

```text
A. Recording-backed song
recording + score/tab → align to recording → Rocksmith CDLC

B. Notation practice song
photo/scan/score only → create deterministic clock → generated practice audio → Rocksmith CDLC
```

For path B, the generated click/backing audio *is* the package audio reference. No attempt to align to an unavailable original recording is required.

## Long-term practice features

After the basic pipeline is reliable, consider:

- progressive tempo ladders (e.g. 60 → 70 → 80 → 90 → 100%);
- automatically advance tempo after user-defined successful repetitions;
- difficult-measure subdivision clicks;
- accent patterns;
- randomized rest/count exercises;
- phrase-based loops inferred from notation;
- generated chord/drum accompaniment styles;
- separate backing mixes for Bass, Lead and Rhythm practice;
- audible cue before loop restart;
- user-created exercise library from selected book measures;
- optional export of the recognized score to MusicXML/MIDI/GP-compatible interchange where legally and technically appropriate;
- comparison of recognized printed notation against a separate Guitar Pro or audio source as independent evidence.

## Definition of success

This roadmap capability succeeds when a user can take a clear picture of a bass or guitar notation/TAB page, review a small number of uncertain recognition decisions, and generate a synchronized Rocksmith 2014 practice arrangement with count-in, click track, and optional generated backing accompaniment without needing the original commercial recording.

The best user experience should approach:

```text
Take picture
  ↓
Review highlighted uncertainties
  ↓
Choose tempo + practice backing
  ↓
Generate
  ↓
Play in Rocksmith
```

## Implementation plan and status

This section is the authoritative, concrete implementation plan for this roadmap capability. It exists so that agent runs which pick this issue back up implement the same agreed scope instead of re-deriving (and re-litigating) it from the narrative sections above. Update this section in place as slices land; do not duplicate it elsewhere.

Real image recognition (OMR/OCR against a photographed page) is out of scope for a single implementation slice — it is its own research spike (phase N0 below) requiring a library/model evaluation before any commitment. The plan therefore builds the pipeline **downstream of recognition** first, against fixture/hand-authored "recognized" data shaped like real recognition output, so every later slice (including the eventual real recognizer) has a working, tested pipeline to plug into rather than needing to be built end-to-end at once.

### Landed

- `src/rocksmith_cdlc_generator/deterministic_tempo_map.py` — `build_deterministic_tempo_map(measure_count, bpm, time_signature_numerator, time_signature_denominator, tempo_changes)` produces a `beats.TempoMap` with no recording anchor: beat 1 of measure 1 starts at `time=0.0`, later beats/measures are computed purely from BPM and time signature, and `TempoChange(measure, bpm)` entries take effect starting at a given measure. Reuses the existing `TempoMap`/`BeatEvent` schema unchanged, so it plugs directly into `rocksmith_xml.py:build_rocksmith_bass_xml`/`build_rocksmith_guitar_xml` without any downstream changes. Mid-song time-signature changes are not yet supported (`TempoMap` only carries one top-level signature) — see "Not yet started" below.
- `src/rocksmith_cdlc_generator/click_track_render.py` — `render_click_track_wav(tempo_map, destination, count_in_measures, subdivision, trailing_seconds)` renders a mono 16-bit PCM WAV click track: count-in measures, downbeat-accented clicks (1800 Hz) vs. regular beat clicks (1200 Hz), and optional eighth/sixteenth subdivision clicks, all computed from the same tempo map arithmetic so chart and click cannot drift relative to each other by construction. The synthesis (25 ms decaying sine burst) mirrors `audio_playback.py`'s existing live-playback click (`ProjectAudioTransport._mix_click`) so the rendered practice audio sounds the same as the desktop app's in-session metronome preview.
- Tests: `tests/test_deterministic_tempo_map.py` (tempo/measure arithmetic, tempo-change boundaries, invalid input rejection) and `tests/test_click_track_render.py` (WAV format, count-in-to-chart-boundary sample alignment, full-arrangement measure-boundary alignment, subdivision clicks, invalid input rejection).

These two modules alone satisfy the doc's "Click-track practice audio" and "Deterministic timing without a commercial recording" sections end-to-end for a synthetic tempo/measure map; they do not yet touch recognition, arrangement generation, or the desktop UI.

### Next slice (not yet started)

In dependency order:

1. **`printed_notation_import.py`** — new adapter mirroring `guitarpro_import.py`'s shape (`*_ADAPTER_ID` constant, `*_adapter_sha256()` fingerprint, a dedicated exception type). Consumes a fixture/JSON description of one recognized bass-TAB page (4-8 measures) and emits `source_import.py`'s `ImportedSource`/`SourceTrack`/`SourceNoteEvent`. `SourceNoteEvent`/`SourceProvenance` need additive fields to carry this doc's `measure`/`beat`/`source.page`/`source.region` provenance (today only a flat `import_confidence` + `trust_class` exist) — extend, do not replace, those models. Document plainly in the module docstring that this is a placeholder standing in for real recognition, not a recognizer.
2. **Authoring bridge** — convert the fixture's recognized events into a `ReviewedExportArrangement` (see `reviewed_export_events.py`) and feed the existing `reviewed_bass_authoring.py` → `reviewed_rocksmith_xml.py` → `build_rocksmith_bass_xml` pipeline, using the `TempoMap` from step (1) above. This is the reuse win: no new XML-generation code, only a new adapter feeding the existing reviewed-authoring boundary.
3. **Validation** — reuse the `eof_rest_boundary_check.py`/`eof_short_note_truncation_check.py` advisory-check pattern for rest/sustain correctness against the generated arrangement; add a click-to-measure-boundary alignment check consuming the same tempo map (the doc's explicit acceptance criterion under "First proof of concept").
4. **Image intake reuse** — register the source page image via the existing `official_tab_reference.py` (hashing, dedupe, per-measure region mapping, rotation), which already solves photo intake/provenance for issue #453's TAB viewer, even though this slice has no OCR to drive automatic region detection (regions are hand-tagged in the fixture for now).
5. **CLI** — `import-notation` subcommand in `cli.py`, mirroring `import-gp`/`import-musicxml` (`project`, source-file flag, `--instrument bass`).
6. **Tests + docs** — `tests/test_printed_notation_import.py` following `tests/test_reviewed_bass_authoring.py`'s style (pydantic construction, invariant-violation `pytest.raises` cases, one golden happy path); update this section once landed.

### Explicitly out of scope until a dedicated slice

- Real image recognition/OMR (phase N0: OMR library/model evaluation, licensing check, staff/TAB-line detection). This is a research spike, not an incremental extension of the above.
- Mid-song time-signature changes in the deterministic tempo map (`TempoMap` schema extension needed).
- Generated drum/harmonic backing audio beyond the click track (doc phase N5).
- Multi-page assembly, measure looping/export variants, tempo-scaling variant packages (doc phases N7-N8).

The user should spend time practicing the music, not manually re-entering an entire notation book.