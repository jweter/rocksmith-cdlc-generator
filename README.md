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
  -> optional bass stem separation boundary
  -> bass transcription baseline
  -> confidence-bearing bass note events
  -> bass_raw.json + bass.mid
  -> bass transcription quality review
  -> four-string bass fret/string mapping
  -> bass_mapped.json + mapping review
```

EOF export and DLC Builder integration remain later stages and are deliberately separated from ingestion, timing analysis, transcription, and mapping.

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
cdlc map-bass "projects\artist-song" --tuning "E Standard" --max-fret 24
cdlc inspect "projects\artist-song"
```

Alternative beat baseline:

```powershell
cdlc tempo "projects\artist-song" --engine librosa-plp
```

### Bass input hierarchy

The transcription stage uses the strongest available input in this order:

1. an explicit `--input` bass stem;
2. `stems/bass.wav` if a generated stem exists;
3. `audio/normalized.wav` as the full-mix fallback.

If a clean bass stem is already available:

```powershell
cdlc transcribe-bass "projects\artist-song" --input "C:\Music\bass-stem.wav"
```

For full-mix material, the project has an optional adapter for the separately installed `audio-separator` CLI. Choose a bass-capable model deliberately rather than relying on a hard-coded model:

```powershell
audio-separator --list_models --list_filter bass
cdlc separate-bass "projects\artist-song" --model "<chosen-model-filename>"
cdlc transcribe-bass "projects\artist-song"
```

`audio-separator` is intentionally not a core dependency because its ML/runtime footprint is much larger than the deterministic project core. The adapter requests one 44.1 kHz WAV Bass stem and stores it as `stems/bass.wav`.

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
analysis/bass_raw.json
analysis/bass_notes.csv
charts/bass.mid
review/bass_transcription_review.json
```

The bass baseline uses onset detection plus pYIN fundamental-frequency estimation. Each note carries overall, pitch, and timing confidence values plus a `review_required` flag. The review artifact reports `PASS`, `WARNING`, or `FAIL` so uncertain output stays visible to the author.

`charts/bass.mid` is an intermediate Standard MIDI File preserving candidate pitch, onset, and duration. It deliberately contains no fret/string choice.

### Bass fret mapping

`cdlc map-bass` consumes `analysis/bass_raw.json` and writes:

```text
charts/bass_mapped.json
review/bass_mapping_review.json
```

The internal string convention is explicit: string `0` is the lowest-pitched bass string and string `3` is the highest. Tunings are represented by open-string MIDI pitches rather than labels alone.

Current built-in tunings:

- E Standard: E1 A1 D2 G2
- Drop D: D1 A1 D2 G2
- Eb Standard: Eb1 Ab1 Db2 Gb2
- D Standard: D1 G1 C2 F2

For every source note the mapper first enumerates every playable string/fret position inside the configured fret range. It then uses dynamic programming over each contiguous playable sequence to minimize a weighted combination of fret movement, string crossing, large position jumps, and unnecessary high-fret use while retaining alternate positions. Unplayable notes are not discarded: they remain in the mapped artifact, are marked for review, and make the mapping review `FAIL`.

## Design rules

1. Source audio is immutable.
2. All derived artifacts are reproducible and hashed.
3. Expensive stages will be cacheable by source hash + configuration + model version.
4. The internal representation remains independent from EOF/DLC Builder.
5. Low-confidence musical guesses must be reviewable rather than silently authoritative.
6. Analysis engines remain replaceable behind adapter contracts and must be benchmarked before becoming defaults.
7. Source separation is optional: structured notation and clean bass stems should bypass it when available.
8. Fret mapping is a sequence optimization problem, not an independent per-note lookup.
