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
Song Preview & Timing Editor
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

## Product architecture

The finished product should be both:

- a **Python-based engine** for deterministic audio analysis, transcription, mapping, validation, tone research, testing, and packaging orchestration;
- a **Windows desktop GUI** for the normal human workflow.

The CLI/library surface remains important as the testable engine and debugging interface. The GUI should become the normal user experience once the core pipeline is stable enough for real-song review.

The intended desktop application is not a thin form wrapper. Its center should be a persistent **Song Workspace** where the user can preview the recording, inspect timing, review generated arrangements, correct uncertain events, approve tones, run validation, and build the package.

PySide6 / Qt is the current preferred GUI direction unless later prototyping demonstrates a materially better Windows option.

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
10. Automatic analysis must be reviewable before it becomes authoritative.
11. Manual edits must be non-destructive and provenance-aware; preserve raw detector/model output separately from reviewed artifacts.
12. The preview/editor should allow most timing and chart quality checks before launching Rocksmith.

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
- Preserve raw detector timing separately from reviewed/corrected timing.
- Make timing artifacts suitable for visualization and manual anchor editing in the future Song Workspace.

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
- Expose validation issues in a form the Song Workspace can jump to directly.

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
- User-owned DRM-free purchases such as iTunes Store AAC, Qobuz FLAC/WAV, and Bandcamp downloads are valid local inputs when the user has the right to use them.

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

### Milestone 10.5 — Tone research and Rocksmith tone reconstruction
- Research song/album/era gear using source-ranked web evidence.
- Prefer direct artist/producer/studio evidence over generic ownership claims.
- Preserve URLs, evidence scope, authority, confidence, and contradictions.
- Infer broad tone/effect families without claiming exact historical equipment when evidence is insufficient.
- Derive the valid Rocksmith 2014 device catalog locally from the user's own Rocksmith installation rather than redistributing Ubisoft-derived gear data.
- Map researched tone families to actual local Rocksmith amp/effect keys and knob defaults.
- Keep a human review gate before tone injection.
- Later detect tone regions/change timestamps and expose them on the Song Workspace timeline.

### Milestone 11 — Song Preview & Timing Editor

The Song Preview & Timing Editor is a first-class product milestone, not optional GUI polish. It is the main human-review surface for finding and correcting problems before packaging or launching Rocksmith.

See `docs/song-preview-timing-editor.md` for the complete specification.

#### V1 synchronized workspace
- Load a local song project.
- Display source/normalized waveform.
- Display detected beat grid, measures/downbeats, local BPM, and sections.
- Play synchronized audio with a moving playhead.
- Click-to-seek and scrub.
- Zoom and navigate the timeline.
- Loop a selected time/measure region.
- Provide song-only, song+click, click-only, and stem+click audition modes.
- Ensure the metronome follows the variable-tempo map rather than a fixed BPM.

#### Beat-map correction
- Select any beat/downbeat.
- Nudge by ±1 ms and ±10 ms.
- Enter exact timestamps.
- Create/remove trusted manual anchors.
- Shift one beat, one measure, or a selected region.
- Refit/interpolate beats between surrounding trusted anchors.
- Recalculate local BPM between anchors.
- Preserve raw automatic timing separately from reviewed timing.
- Make corrections reversible and provenance-aware.

#### Timing diagnostics
- Surface low-confidence beats.
- Flag unexplained abrupt BPM changes.
- Detect likely accumulated drift.
- Compare multiple beat trackers where useful.
- Flag symbolic-source/audio timing disagreements.
- Surface note-onset clusters that appear consistently offset from the beat grid.
- Prioritize suspicious regions in the review queue.

#### Arrangement preview
- Show Bass, Lead, and Rhythm events on the same synchronized timeline.
- Show note/chord onset, duration, pitch, string/fret, techniques, source trust, confidence, and review state.
- Allow correction of note timing and physical mapping from the workspace.
- Jump directly between review-required events.

#### Virtual fretboard
- Synchronize current/upcoming notes to a Bass/guitar fretboard.
- Respect the arrangement's actual tuning.
- Highlight active notes/chords and hand positions.
- Show alternate string/fret candidates.
- Allow the user to choose a corrected physical position.
- Use the fretboard to expose musically implausible jumps even when pitches are correct.

#### Confidence and review visualization
- High-confidence automatic content must be visually distinct from moderate/low-confidence content.
- User-confirmed content must be visually distinct from generated content.
- Unresolved blocking issues must remain obvious.
- No low-confidence event should silently look authoritative.

#### Sections, phrases, and tone markers
- Display intro/verse/chorus/bridge/solo/etc. section boundaries.
- Allow rename/add/delete/move/lock operations.
- Reuse sections as loop ranges.
- Later display Rocksmith phrase/handshape/anchor data on the same timeline.
- Display tone changes such as Clean → Crunch → Lead Solo and allow transition timing review/approval.

#### GUI workflow

```text
Generate draft
    ↓
Open Song Workspace
    ↓
Song + click timing review
    ↓
Correct/lock beat anchors
    ↓
Review low-confidence notes/chords
    ↓
Review fretboard mapping
    ↓
Review techniques
    ↓
Review sections/phrases
    ↓
Review tone regions/components
    ↓
Run PASS/WARNING/FAIL validation
    ↓
Export/package
```

#### V1 acceptance criteria
A user can:

- open a project;
- see waveform + beat grid;
- play the song with a variable-tempo click;
- select/loop a region;
- hear and see a bad beat map;
- move a downbeat;
- lock trusted anchors;
- refit beats between anchors;
- save reviewed timing without destroying raw analysis;
- rerun validation against reviewed timing;
- reopen the project with all timing edits intact.

### Milestone 12 — Full Windows desktop application
- Build the normal end-user workflow around the Song Workspace.
- Add project creation/import wizard and drag/drop audio.
- Add arrangement selection (Bass/Lead/Rhythm).
- Show pipeline progress by stage.
- Expose PASS/WARNING/FAIL status and review queues.
- Provide metadata, tone evidence, source citations, and build controls.
- Keep PowerShell/CLI use optional for normal operation.
- Package as a normal Windows executable/installer when the engine and review workflow are stable.

## GUI implementation order

1. Stable normalized-audio + beat-map artifacts.
2. Minimal PySide6/Qt Song Workspace shell.
3. Waveform + audio playback + variable-tempo metronome.
4. Beat-grid rendering + manual anchor editing.
5. Looping + timing diagnostics.
6. Bass note overlay/event correction.
7. Virtual fretboard.
8. Lead/Rhythm overlays.
9. Technique/section/phrase review.
10. Tone-region and real Rocksmith component review.
11. Validation/build controls.
12. Packaged Windows executable.

The GUI should begin once the underlying timing artifacts are sufficiently stable to support real correction work. Do not wait until every advanced transcription feature is complete: the timing editor directly improves benchmark quality and human correction time.

## Testing strategy

- Unit tests for deterministic transforms and validators.
- Integration tests across adjacent pipeline stages.
- Golden tests using 5–20 second synthetic/original/public-domain/licensed fixtures.
- At least one variable-tempo fixture.
- Cross-tool compatibility tests for Rocksmith XML and DLC Builder project contracts.
- Timing-editor tests for manual anchors, interpolation/refit, undo/reload, and preservation of raw timing.
- GUI tests should focus on state/data correctness rather than pixel-perfect rendering.
- Never store commercial song audio or proprietary tab dumps in the repository.

## Performance and runtime constraints

- Target Windows 11 and CPU-capable execution.
- No GPU assumption.
- Execute heavy stages sequentially and release model memory between stages.
- Cache expensive outputs by source SHA + configuration + model/version.
- Keep core Python runtime small; isolate incompatible model runtimes behind subprocess/adapters.
- Audio playback and timeline editing must remain responsive even when heavy ML models are not loaded.
- The Song Workspace should consume cached artifacts rather than keeping separation/transcription models resident.

## Success metric

The primary product metric is **human editing minutes per finished song minute** compared with a manual Rocksmith authoring workflow. Model accuracy, review-flag count, build success rate, reproducibility, and the number of errors caught before launching Rocksmith are supporting metrics.

The preview/editor is successful when it lets the user catch and correct timing, transcription, fret-mapping, and tone-transition problems faster than discovering them through repeated in-game package testing.
