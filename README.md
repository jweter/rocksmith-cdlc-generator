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
  -> tempo_map.json + beats.csv
  -> beat-grid quality review
  -> bass transcription baseline
  -> confidence-bearing bass note events
  -> bass transcription quality review
```

Fretboard mapping, EOF export, and DLC Builder integration remain later stages and are deliberately separated from ingestion, timing analysis, and transcription.

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
cdlc --help
cdlc new --audio "C:\Music\song.flac" --artist "Artist" --title "Song" --instrument bass
cdlc normalize "projects\artist-song"
cdlc tempo "projects\artist-song" --engine librosa
cdlc transcribe-bass "projects\artist-song" --engine librosa-pyin
cdlc inspect "projects\artist-song"
```

Alternative beat baseline:

```powershell
cdlc tempo "projects\artist-song" --engine librosa-plp
```

If a clean bass stem is already available, bypass full-mix transcription explicitly:

```powershell
cdlc transcribe-bass "projects\artist-song" --input "C:\Music\bass-stem.wav"
```

`cdlc new` never modifies the original audio. It creates a project workspace, copies the source into `source/`, records hashes and metadata, and writes `project.json`.

`cdlc normalize` creates `audio/normalized.wav` as 44.1 kHz stereo PCM and records the FFmpeg command and output hash.

`cdlc tempo` analyzes `audio/normalized.wav` and writes:

```text
analysis/tempo_map.json
analysis/beats.csv
review/beat_grid_review.json
```

`cdlc transcribe-bass` writes:

```text
analysis/bass_notes.json
analysis/bass_notes.csv
review/bass_transcription_review.json
```

The bass baseline uses onset detection plus pYIN fundamental-frequency estimation. Each note carries overall, pitch, and timing confidence values plus a `review_required` flag. The review artifact reports `PASS`, `WARNING`, or `FAIL` so uncertain output stays visible to the author.

## Design rules

1. Source audio is immutable.
2. All derived artifacts are reproducible and hashed.
3. Expensive stages will be cacheable by source hash + configuration + model version.
4. The internal representation remains independent from EOF/DLC Builder.
5. Low-confidence musical guesses must be reviewable rather than silently authoritative.
6. Analysis engines remain replaceable behind adapter contracts and must be benchmarked before becoming defaults.
7. Source separation is optional: structured notation and clean bass stems should bypass it when available.
