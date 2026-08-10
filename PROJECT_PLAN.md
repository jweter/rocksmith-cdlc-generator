# Rocksmith CDLC Generator — Project Plan

This file is the canonical implementation roadmap. The design goal is a local-first, reproducible assistant that produces high-quality first-draft Rocksmith 2014 Remastered arrangements while keeping uncertain musical decisions visible for human review.

## Core pipeline

```text
source audio / stems / notation / existing custom chart
        ↓
project ingest + immutable provenance
        ↓
working audio + timing analysis
        ↓
transcription and/or symbolic source import
        ↓
source reconciliation + human review
        ↓
string/fret mapping
        ↓
unified validation gate
        ↓
Rocksmith XML / DLC Builder project
        ↓
DLC Builder / Rocksmith2014.NET packaging
        ↓
staged and verified .psarc
        ↓
manual approval before installation
```

## Governing rules

1. Source files are immutable.
2. The canonical arrangement representation is independent of EOF, DLC Builder, and PSARC.
3. Every uncertain generated event must retain provenance, confidence, and review state.
4. Prefer structured notation over isolated stems, and isolated stems over full-mix transcription when available.
5. Packaging is prohibited while unified validation is `FAIL`.
6. Generation and testing never modify the live Rocksmith installation, player profile, or official DLC.
7. Do not commit or distribute copyrighted commercial audio, stems, or tabs without appropriate rights.
8. Heavy ML runtimes remain replaceable behind adapters and should run sequentially on 16 GB systems.
9. Benchmark human correction time per finished song minute, not only model accuracy.

## Milestones

### Milestone 0 — Toolchain and architecture proof
- Record toolchain decisions and compatibility boundaries.
- Confirm Python 3.12 core, FFmpeg, EOF/Rocksmith XML, DLC Builder/Rocksmith2014.NET handoff.

### Milestone 1 — Project skeleton
- `src/`, `tests/`, `docs/`, `samples/`, `README.md`, `PROJECT_PLAN.md`.
- Working `cdlc --help` entry point and CI.

### Milestone 2 — Audio ingest and reproducibility
- Create project directories and manifest.
- Preserve original audio.
- SHA-256 source identity.
- Normalize to 44.1 kHz stereo PCM WAV.
- Record provenance and FFmpeg command.

### Milestone 3 — Beat and tempo mapping
- Detect beats/downbeats and time signature.
- Support tempo drift/change rather than assuming a single BPM forever.
- Produce human-reviewable timing artifacts and objective timing benchmarks.

### Milestone 4 — Bass transcription
- Prefer explicit bass stem, then generated bass stem, then full mix.
- Produce confidence-bearing note onset, pitch, duration, and rest information.
- Write `bass_raw.json` and intermediate `bass.mid`.

### Milestone 5 — Bass fret/string mapping
- Enumerate all playable positions.
- Optimize complete phrases rather than greedily mapping each note.
- Support E Standard, Drop D, Eb Standard, D Standard, and later custom tunings.
- Preserve alternatives and mapping confidence.

### Milestone 6 — Unified validation and review queue
- Validate timing, song bounds, overlaps, tuning, fret limits, mapping integrity, and confidence.
- Produce prioritized human review flags.
- Enforce PASS/WARNING/FAIL packaging gate.

### Milestone 7 — Authoring and DLC Builder bridge
- Export validation-gated Rocksmith 2014 Bass XML.
- Generate deterministic `.rs2dlc` DLC Builder projects.
- Delegate WEM, SNG, manifests, Dynamic Difficulty processing, and PSARC construction to established Rocksmith2014.NET tooling rather than reimplementing them in Python.

### Milestone 8 — First playable generated Bass CDLC
- Verify all `.rs2dlc` references and hashes before packaging.
- Keep packaging output in project-local staging.
- Launch/open DLC Builder only after readiness checks.
- Register and hash produced `.psarc` files.
- Verify PSARC signature/basic integrity before any manual installation.
- Complete one end-to-end Bass song and record correction time, failures, and lessons learned.

### Milestone 8.5 — Source Import & Reconciliation
This is a high-priority expansion before lead-guitar transcription. Structured notation should reduce uncertainty and human editing substantially when a legitimate source is available.

#### Input adapters
- Guitar Pro `.gp3`, `.gp4`, `.gp5` import.
- MusicXML import.
- Standard MIDI import.
- Deliberately selected existing custom Rocksmith `.psarc` import through Rocksmith2014.NET-compatible tooling.
- User-provided isolated stems and local audio remain first-class inputs.

#### Metadata and audio acquisition
- MusicBrainz metadata lookup/identification for artist, recording, release, album, and year.
- Local WAV/FLAC/MP3/M4A drag/drop or CLI import.
- Pluggable licensed/public-domain audio providers; Jamendo is a candidate for legal end-to-end fixtures and user-authorized downloads.
- Downloadable direct URLs only where rights/terms permit.
- No Spotify/Apple Music/YouTube ripping and no scraping/bypassing paid tab download features.

#### Canonical source priority
1. Structured notation aligned to the recording.
2. Existing user-supplied Rocksmith/custom chart.
3. Isolated instrument stem.
4. Full-mix audio transcription.

#### Reconciliation engine
- Convert every symbolic source to the neutral internal event model.
- Align symbolic timing to the analyzed recording rather than blindly trusting tab tempo.
- Compare imported pitch/rhythm/string/fret information against audio-derived evidence.
- Preserve exact source fingering when credible; use the mapper when fingering is absent or impossible.
- Generate disagreement flags instead of silently choosing one source.
- Track provenance per note: source file, imported/generated method, confidence, and any corrections.

#### Proposed CLI
```text
cdlc identify PROJECT
cdlc import-notation PROJECT --file song.gp5
cdlc import-chart PROJECT --psarc custom.psarc
cdlc reconcile PROJECT --instrument bass
```

#### Planned artifacts
```text
imports/source_manifest.json
imports/notation_raw.json
imports/rocksmith_raw.json
analysis/alignment.json
charts/bass_reconciled.json
review/source_disagreements.json
```

#### Acceptance criteria
- Import a legal/synthetic GP/MusicXML/MIDI fixture and preserve pitches, durations, and available fingering.
- Align an intentionally offset notation fixture to audio within a measured tolerance.
- Detect deliberately inserted source/audio disagreements.
- Demonstrate that a credible symbolic Bass source reduces review flags and manual correction time relative to audio-only transcription.

See `docs/source_import_plan.md` for the detailed implementation sequence.

### Milestone 9 — Lead guitar
- Single-note lead transcription first.
- Extend mapping and validation to six-string guitar.
- Preserve conservative technique detection and review requirements.

### Milestone 10 — Rhythm, chords, and techniques
- Add polyphonic/chord recognition only after monophonic workflows are benchmarked.
- Add slides, bends, hammer-ons/pull-offs, palm mute, harmonics, vibrato, etc. conservatively.

## Testing strategy

- Unit tests for deterministic transforms and validators.
- Integration tests across adjacent pipeline stages.
- Golden tests using 5–20 second synthetic/original/public-domain/licensed fixtures.
- At least one variable-tempo fixture.
- Cross-tool compatibility tests for Rocksmith XML and DLC Builder project contracts.
- Never store commercial song audio or proprietary tab dumps in the repository.

## Performance and runtime constraints

- Target Windows 11 and CPU-capable execution.
- No GPU assumption.
- Execute heavy stages sequentially and release model memory between stages.
- Cache expensive outputs by source SHA + configuration + model/version.
- Keep core Python runtime small; isolate incompatible model runtimes behind subprocess/adapters.

## Success metric

The primary product metric is **human editing minutes per finished song minute** compared with a manual Rocksmith authoring workflow. Model accuracy, review-flag count, build success rate, and reproducibility are supporting metrics.