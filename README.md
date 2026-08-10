# Rocksmith CDLC Generator

Local-first, confidence-aware tooling for generating high-quality first-draft Rocksmith 2014 Remastered arrangements.

## Current scope

The current implementation covers:

```text
source audio
  -> inspect + SHA-256
  -> immutable source copy
  -> normalized 44.1 kHz PCM WAV
  -> project manifest + provenance
  -> beat/tempo analysis
  -> optional bass stem separation
  -> bass transcription
  -> optional MIDI / Guitar Pro symbolic source import
  -> four-string bass fret/string mapping
  -> unified PASS/WARNING/FAIL validation gate
  -> validation-gated Rocksmith 2014 Bass XML
  -> DLC Builder .rs2dlc project handoff
  -> build-readiness staging + asset hashing
  -> staged PSARC registration + basic header verification
```

Final WEM/SNG/PSARC construction remains delegated to DLC Builder / Rocksmith2014.NET. The generator never writes directly to the live Rocksmith installation during generation, staging, or verification.

See `PROJECT_PLAN.md` for the canonical roadmap and `docs/source_import_plan.md` for Milestone 8.5.

## Requirements

- Windows 11
- Python 3.12+
- FFmpeg and ffprobe on PATH

## Setup

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[dev,beat]"
```

Guitar Pro 3/4/5 import is optional:

```powershell
pip install -e ".[guitarpro]"
```

The adapter uses PyGuitarPro 0.11, which supports GP3, GP4, and GP5. Newer Guitar Pro formats are intentionally not claimed by this adapter.

## CLI

```powershell
cdlc new --audio "C:\Music\song.flac" --artist "Artist" --title "Song" --instrument bass
cdlc normalize "projects\artist-song"
cdlc tempo "projects\artist-song" --engine librosa
cdlc import-midi "projects\artist-song" --midi "C:\Tabs\song.mid"
cdlc import-gp "projects\artist-song" --gp "C:\Tabs\song.gp5"
cdlc transcribe-bass "projects\artist-song" --engine librosa-pyin
cdlc map-bass "projects\artist-song" --tuning "E Standard" --max-fret 24
cdlc validate "projects\artist-song"
cdlc export "projects\artist-song" --target rocksmith-xml --instrument bass
cdlc prepare-dlcbuilder "projects\artist-song" --album "Album" --year 2026 --cover "C:\Music\cover.png"
cdlc stage-build "projects\artist-song"
cdlc launch-dlcbuilder "projects\artist-song" --executable "C:\Path\To\DLCBuilder.exe"
cdlc register-psarc "projects\artist-song" --psarc "C:\Staging\Song_p.psarc"
```

### Symbolic source import

`import-midi` and `import-gp` both write the versioned neutral source contract beneath `sources/imported/`. Import fidelity and musical truth remain separate: a correctly parsed symbolic note is still `symbolic_unverified` until alignment/reconciliation checks it against the recording.

Guitar Pro import preserves explicit tuning, string/fret positions, pitch, written-score timing, detected tempo changes, time signatures, and conservative technique annotations. Automatic Bass-track selection uses track name, General MIDI Bass program, string count, and range. If selection is ambiguous, the importer refuses to guess and requires `--track-index`.

GP repeat structures are currently preserved in written-score order rather than silently expanded; the imported artifact carries a warning. Non-four-string Bass tracks are also preserved in the neutral model and warned because current Rocksmith Bass export targets four strings.

### Build staging

`prepare-dlcbuilder` writes a deterministic `.rs2dlc` project beneath `build/dlcbuilder/`. If `--preview` is omitted, FFmpeg generates a 30-second 44.1 kHz PCM preview beginning at `--preview-start`.

`stage-build` runs the packaging gate, resolves every DLC Builder file reference, and records SHA-256 hashes and sizes in `build/staging/build_readiness.json`.

`launch-dlcbuilder` performs the same readiness checks before opening the selected `.rs2dlc` file. `register-psarc` verifies the returned PSARC signature/header, hashes it, and stages it project-locally without installing it.

## Key outputs

```text
sources/imported/<source>-<sha>.json
analysis/tempo_map.json
analysis/bass_raw.json
charts/bass.mid
charts/bass_mapped.json
review/validation_report.json
eof/arr_bass_RS2.xml
build/dlcbuilder/<DLCKey>.rs2dlc
build/staging/build_readiness.json
build/staging/psarc_receipt.json
```

## Design rules

1. Source audio is immutable.
2. Derived artifacts remain reproducible and confidence-aware.
3. The internal arrangement model stays independent from EOF/DLC Builder.
4. Low-confidence musical guesses must remain reviewable.
5. Packaging/export is blocked on validation `FAIL`.
6. The generator does not invent unsupported metadata or musical techniques.
7. DLC Builder/Rocksmith2014.NET remains responsible for WEM, SNG, manifests, and PSARC construction.
8. Nothing in this pipeline modifies the live Rocksmith installation or player profile.
9. Structured notation should be preferred over audio-only transcription when legitimately available and alignable to the recording.
10. Imported symbolic and audio-derived evidence must be reconciled transparently; disagreements become review items rather than silent overwrites.
