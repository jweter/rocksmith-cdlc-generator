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
  -> four-string bass fret/string mapping
  -> unified PASS/WARNING/FAIL validation gate
  -> validation-gated Rocksmith 2014 Bass XML
  -> DLC Builder .rs2dlc project handoff
  -> build-readiness staging + asset hashing
  -> staged PSARC registration + basic header verification
```

Final WEM/SNG/PSARC construction remains delegated to DLC Builder / Rocksmith2014.NET. The generator never writes directly to the live Rocksmith installation during generation, staging, or verification.

See `PROJECT_PLAN.md` for the canonical roadmap. The roadmap now includes **Milestone 8.5 — Source Import & Reconciliation**, covering Guitar Pro, MusicXML, MIDI, selected custom PSARC input, metadata identification, legal/licensed audio providers, timing alignment, and source-vs-audio reconciliation. The implementation sequence is in `docs/source_import_plan.md`.

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

## CLI

```powershell
cdlc new --audio "C:\Music\song.flac" --artist "Artist" --title "Song" --instrument bass
cdlc normalize "projects\artist-song"
cdlc tempo "projects\artist-song" --engine librosa
cdlc transcribe-bass "projects\artist-song" --engine librosa-pyin
cdlc map-bass "projects\artist-song" --tuning "E Standard" --max-fret 24
cdlc validate "projects\artist-song"
cdlc export "projects\artist-song" --target rocksmith-xml --instrument bass
cdlc prepare-dlcbuilder "projects\artist-song" --album "Album" --year 2026 --cover "C:\Music\cover.png"
cdlc stage-build "projects\artist-song"
cdlc launch-dlcbuilder "projects\artist-song" --executable "C:\Path\To\DLCBuilder.exe"
cdlc register-psarc "projects\artist-song" --psarc "C:\Staging\Song_p.psarc"
```

`prepare-dlcbuilder` writes a deterministic `.rs2dlc` project beneath `build/dlcbuilder/`. If `--preview` is omitted, FFmpeg generates a 30-second 44.1 kHz PCM preview beginning at `--preview-start` (default 30 seconds).

`stage-build` runs the unified packaging gate again, resolves every DLC Builder file reference, and records SHA-256 hashes and sizes in `build/staging/build_readiness.json`. It also writes manual packaging instructions. No live Rocksmith path is involved.

`launch-dlcbuilder` performs the same readiness checks before opening the selected `.rs2dlc` file in DLC Builder. Packaging remains a deliberate external step rather than an undocumented UI automation hack.

`register-psarc` accepts the package built outside Rocksmith, verifies the `.psarc` extension, `PSAR` archive signature, and `zlib` header, hashes it, copies it into project-local staging, and writes `build/staging/psarc_receipt.json`. It does not install the package.

The `.rs2dlc` format follows Rocksmith2014.NET's current DLCProject serialization contract. The Bass arrangement uses `Name = 3`, `RouteMask = 4`, Rocksmith tuning offsets, and stable Master/Persistent IDs derived from source SHA-256. Relative paths are written from the `.rs2dlc` location exactly as DLC Builder expects.

Album, year, artwork, and artist/title metadata are never invented. The authoring export also deliberately omits unsupported techniques, chords, anchors, tones, and Dynamic Difficulty.

## Key outputs

```text
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
9. Structured notation should be preferred over audio-only transcription when it is legitimately available and can be aligned to the recording.
10. Imported symbolic and audio-derived evidence must be reconciled transparently; disagreements become review items rather than silent overwrites.
