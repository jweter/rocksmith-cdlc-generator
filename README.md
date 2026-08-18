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
  -> optional MIDI / Guitar Pro / MusicXML / selected PSARC source import
  -> symbolic-to-audio alignment
  -> symbolic/audio Bass reconciliation
  -> four-string bass fret/string mapping with valid symbolic fingering preserved
  -> unified PASS/WARNING/FAIL validation + source disagreement review
  -> validation-gated Rocksmith 2014 Bass XML with supported imported techniques
  -> DLC Builder .rs2dlc project handoff
  -> build-readiness staging + asset hashing
  -> staged PSARC registration + basic header verification
```

Final WEM/SNG/PSARC construction remains delegated to DLC Builder / Rocksmith2014.NET. The generator never writes directly to the live Rocksmith installation during generation, staging, import, or verification.

`PROJECT_PLAN.md` is the canonical roadmap. Bass, Lead Guitar, and Rhythm Guitar are equal first-class product targets even when one path is technically easier to prove first.

For autonomous/scheduled development, read `AGENTS.md` first, then `docs/project-status.yaml` and `docs/agent-development-policy.md`. The status file is a deliberately maintained continuity cache and must be updated whenever project reality changes.

## Requirements

- Windows 11
- Python 3.12+
- FFmpeg and ffprobe on PATH

Selected PSARC import additionally uses a small .NET 10 bridge pinned to a known Rocksmith2014.NET commit.

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

To enable PSARC import, install the .NET 10 SDK once and build the pinned bridge:

```powershell
.\scripts\bootstrap_psarc_bridge.ps1
```

The bootstrap clones Rocksmith2014.NET commit `b87c9a3afd31c40ade9685a9244e718e7581c0cb` into gitignored `.tools/` and builds `tools/psarc_bridge/RocksmithPsarcBridge.dll`. Upstream source is not vendored into this repository.

## CLI

```powershell
cdlc new --audio "C:\Music\song.flac" --artist "Artist" --title "Song" --instrument bass
cdlc normalize "projects\artist-song"
cdlc tempo "projects\artist-song" --engine librosa
cdlc import-midi "projects\artist-song" --midi "C:\Tabs\song.mid"
cdlc import-gp "projects\artist-song" --gp "C:\Tabs\song.gp5"
cdlc import-musicxml "projects\artist-song" --musicxml "C:\Tabs\song.musicxml"
cdlc import-psarc "projects\artist-song" --psarc "C:\Customs\Song_p.psarc"
cdlc transcribe-bass "projects\artist-song" --engine librosa-pyin
cdlc align-source "projects\artist-song" --source "projects\artist-song\sources\imported\song-<sha>.json"
cdlc reconcile-bass "projects\artist-song" --source "projects\artist-song\sources\imported\song-<sha>.json"
cdlc map-bass "projects\artist-song" --source auto --tuning "E Standard" --max-fret 24
cdlc validate "projects\artist-song"
cdlc export "projects\artist-song" --target rocksmith-xml --instrument bass
cdlc prepare-dlcbuilder "projects\artist-song" --album "Album" --year 2026 --cover "C:\Music\cover.png"
cdlc stage-build "projects\artist-song"
cdlc launch-dlcbuilder "projects\artist-song" --executable "C:\Path\To\DLCBuilder.exe"
cdlc register-psarc "projects\artist-song" --psarc "C:\Staging\Song_p.psarc"
```

### Symbolic source import and reconciliation

`import-midi`, `import-gp`, `import-musicxml`, and `import-psarc` write the versioned neutral source contract beneath `sources/imported/`. Import fidelity and musical truth remain separate: a correctly decoded note is still `symbolic_unverified` until alignment/reconciliation checks it against the recording.

`import-psarc` only reads the `.psarc` explicitly supplied on the command line. It does not scan Rocksmith directories. The pinned Rocksmith2014.NET bridge performs PSARC/SNG decoding in a temporary directory; Python converts the reconstructed Bass XML into the neutral source model and the temporary extraction is deleted. The original package is never modified.

PSARC import preserves the exact Rocksmith ebeat grid, tuning, string/fret positions, note timing, and directly recoverable single-note techniques. Song packs or ambiguous packages are refused. Bass chords/double-stops are currently surfaced as warnings rather than silently flattened.

`align-source` prefers an imported explicit beat grid when one exists; otherwise it derives a beat grid from symbolic tempo events. `reconcile-bass` compares aligned symbolic notes with `analysis/bass_raw.json`, writing `charts/bass_reconciled.json` and `review/source_disagreements.json`.

`map-bass --source auto` prefers the reconciled chart when present. Use `--source raw` to force the original audio-only path, or `--source reconciled` to require reconciliation. Valid symbolic string/fret positions are preserved; inconsistent positions fall back to inference and remain review-required.

Guitar Pro import preserves explicit tuning, string/fret positions, pitch, written-score timing, detected tempo changes, time signatures, and conservative technique annotations. GP repeat structures are currently preserved in written-score order rather than silently expanded; the imported artifact carries a warning. Non-four-string Bass tracks are also preserved in the neutral model and warned because current Rocksmith Bass export targets four strings.

Rocksmith XML currently exports imported `palm_mute`, `harmonic`, `tremolo_picking`, `vibrato`, `accent`, and `heavy_accent` when present. Techniques needing additional information such as slide targets, bend curves, or HOPO direction remain explicit validation warnings instead of being invented.

### Build staging

`prepare-dlcbuilder` writes a deterministic `.rs2dlc` project beneath `build/dlcbuilder/`. If `--preview` is omitted, FFmpeg generates a 30-second 44.1 kHz PCM preview beginning at `--preview-start`.

`stage-build` runs the packaging gate, resolves every DLC Builder file reference, and records SHA-256 hashes and sizes in `build/staging/build_readiness.json`.

`launch-dlcbuilder` performs the same readiness checks before opening the selected `.rs2dlc` file. `register-psarc` verifies the returned PSARC signature/header, hashes it, and stages it project-locally without installing it.

## Key outputs

```text
sources/imported/<source>-<sha>.json
analysis/tempo_map.json
analysis/bass_raw.json
analysis/alignment.json
charts/bass.mid
charts/bass_reconciled.json
charts/bass_mapped.json
review/source_disagreements.json
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
7. DLC Builder/Rocksmith2014.NET remains responsible for WEM, SNG, manifests, PSARC construction, and PSARC/SNG decoding.
8. Nothing in this pipeline modifies the live Rocksmith installation or player profile.
9. Structured notation should be preferred over audio-only transcription when legitimately available and alignable to the recording.
10. Imported symbolic and audio-derived evidence must be reconciled transparently; disagreements become review items rather than silent overwrites.
