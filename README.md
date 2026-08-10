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
  -> optional bass stem separation boundary
  -> bass transcription baseline
  -> bass_raw.json + bass.mid
  -> four-string bass fret/string mapping
  -> bass_mapped.json
  -> unified PASS/WARNING/FAIL validation gate
  -> prioritized human review queue
  -> validation-gated Rocksmith 2014 Bass XML authoring export
```

DLC Builder project automation and final `.psarc` packaging remain later stages.

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
cdlc validate "projects\artist-song"
cdlc export "projects\artist-song" --target rocksmith-xml --instrument bass
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

For full-mix material, the project has an optional adapter for the separately installed `audio-separator` CLI:

```powershell
audio-separator --list_models --list_filter bass
cdlc separate-bass "projects\artist-song" --model "<chosen-model-filename>"
cdlc transcribe-bass "projects\artist-song"
```

`audio-separator` is intentionally not a core dependency because its ML/runtime footprint is much larger than the deterministic project core.

### Bass transcription

`cdlc transcribe-bass` writes:

```text
analysis/bass_raw.json
analysis/bass_notes.csv
charts/bass.mid
review/bass_transcription_review.json
```

The native baseline uses onset detection plus pYIN fundamental-frequency estimation. Each note carries overall, pitch, and timing confidence plus a `review_required` flag.

### Bass fret mapping

`cdlc map-bass` consumes `analysis/bass_raw.json` and writes:

```text
charts/bass_mapped.json
review/bass_mapping_review.json
```

String `0` is the lowest-pitched bass string and string `3` is the highest. Built-in tunings are E Standard, Drop D, Eb Standard, and D Standard. The mapper enumerates every playable string/fret candidate, then uses dynamic programming over each contiguous phrase to minimize movement and awkward position changes while retaining alternates and confidence.

### Unified validation and review queue

`cdlc validate` is the downstream export/packaging gate. It checks required artifacts and validates song bounds, low-confidence beats, bass overlaps, unresolved transcription notes, playable string/fret mapping, tuning consistency, fret limits, and mapping pitch integrity.

It writes:

```text
review/validation_report.json
review/flags.json
review/summary.md
```

The queue is ordered by severity/priority so hard failures appear before ordinary warnings. A `FAIL` validation exits with status code `2` and sets `can_package=false`.

### Rocksmith authoring export

`cdlc export PROJECT --target rocksmith-xml --instrument bass` requires a non-failing unified validation state and writes:

```text
eof/arr_bass_RS2.xml
eof/export_manifest.json
eof/README.md
```

The XML follows the Rocksmith 2014 instrumental arrangement shape used by current Rocksmith2014.NET/DLC Builder fixtures: song schema version 7, embedded beats, tuning offsets, time-signature event, one difficulty level, and mapped bass notes with string/fret/sustain timing.

This bridge is intentionally conservative. It emits only data the generator actually knows. Milestone 7 does not invent guitar techniques, chords, anchors, tones, or Dynamic Difficulty, and it currently emits one full-song phrase/section until section analysis exists. These limitations are repeated in `eof/export_manifest.json` so they remain visible downstream.

## Design rules

1. Source audio is immutable.
2. All derived artifacts are reproducible and hashed.
3. Expensive stages will be cacheable by source hash + configuration + model version.
4. The internal representation remains independent from EOF/DLC Builder.
5. Low-confidence musical guesses must be reviewable rather than silently authoritative.
6. Analysis engines remain replaceable behind adapter contracts and must be benchmarked before becoming defaults.
7. Source separation is optional: structured notation and clean bass stems should bypass it when available.
8. Fret mapping is a sequence optimization problem, not an independent per-note lookup.
9. Downstream authoring export and packaging are prohibited while unified validation status is `FAIL`.
10. Interchange exporters must not invent unsupported musical information merely to satisfy a downstream format.
