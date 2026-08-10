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
```

Final WEM/SNG/PSARC packaging remains delegated to DLC Builder / Rocksmith2014.NET.

See `PROJECT_PLAN.md` for the full roadmap.

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
```

`prepare-dlcbuilder` writes a deterministic `.rs2dlc` project beneath `build/dlcbuilder/`. If `--preview` is omitted, FFmpeg generates a 30-second 44.1 kHz PCM preview beginning at `--preview-start` (default 30 seconds).

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
