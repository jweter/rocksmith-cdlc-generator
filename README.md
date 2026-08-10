# Rocksmith CDLC Generator

Local-first, confidence-aware tooling for generating high-quality first-draft Rocksmith 2014 Remastered arrangements.

## Current scope

The first implementation milestone intentionally stops at:

```text
source audio
  -> inspect + SHA-256
  -> immutable source copy
  -> normalized 44.1 kHz PCM WAV
  -> project manifest + provenance
```

Bass transcription, beat tracking, fretboard mapping, EOF export, and DLC Builder integration are later stages and are deliberately not coupled to ingestion.

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
pip install -e ".[dev]"
```

## CLI

```powershell
cdlc --help
cdlc new --audio "C:\Music\song.flac" --artist "Artist" --title "Song" --instrument bass
cdlc normalize "projects\artist-song"
cdlc inspect "projects\artist-song"
```

`cdlc new` never modifies the original audio. It creates a project workspace, copies the source into `source/`, records hashes and metadata, and writes `project.json`.

`cdlc normalize` creates `audio/normalized.wav` as 44.1 kHz stereo PCM and records the FFmpeg command and output hash.

## Design rules

1. Source audio is immutable.
2. All derived artifacts are reproducible and hashed.
3. Expensive stages will be cacheable by source hash + configuration + model version.
4. The internal representation remains independent from EOF/DLC Builder.
5. Low-confidence musical guesses must be reviewable rather than silently authoritative.
