# Multi-Channel Audio Evidence Pipeline

## Purpose
Define a governed architecture for combining stem separation, audio-to-MIDI transcription, speech alignment, and DSP into independent evidence channels that can improve Rocksmith arrangement review without replacing human-confirmed score authority.

Primary candidates:
- Demucs lineage / actively maintained stem-separation implementations;
- StemSplit as an automation-friendly local separation option;
- Spotify Basic Pitch for candidate note/MIDI evidence;
- WhisperX for vocal/lyric timing evidence;
- librosa for deterministic DSP features.

## Core rule
External analysis produces **evidence**, not canonical arrangement state.

```text
GP5 / score mapping (human-confirmed authority)
                 |
                 v
           candidate arrangement
                 ^
                 |
Master audio -> stem separation
                 |
        +--------+--------+
        |        |        |
      bass     guitar    vocals
        |        |        |
   Basic Pitch Basic Pitch WhisperX
        |        |        |
        +--------+--------+
                 |
          evidence comparison
                 |
        confidence + review
```

## Phase 1: stem-separation experiment
Create an optional `StemProvider` boundary. Compare at least one actively maintained Demucs-derived implementation and StemSplit/local ONNX where practical.

Required outputs:
- source audio hash;
- provider/version/model;
- stem role;
- output hash/path;
- processing parameters;
- warnings/errors.

Never commit copyrighted stem audio to the repository.

## Phase 2: note-evidence adapters
Run Basic Pitch only on appropriate isolated stems where possible. Convert output into a Rocksmith-owned `AudioNoteEvidence` representation containing:
- onset/offset;
- pitch/MIDI note;
- confidence where available;
- source stem identity;
- provider/model/version;
- provenance to master recording hash.

Do not map evidence directly into final arrangement events.

## Phase 3: vocal evidence
WhisperX remains an optional `VocalTimingEvidence` source for lyric/phrase/speech regions. It must never become note timing authority.

## Phase 4: deterministic DSP
Use librosa or equivalent deterministic DSP primitives for:
- onset strength;
- beat/tempo candidates;
- chroma/CQT features;
- spectral diagnostics;
- cross-correlation or alignment support.

These features should be cached/provenanced by input hash and parameters.

## Phase 5: evidence comparison
Build a review layer that compares score-derived events against audio-derived evidence without silently changing them.

Possible outcomes:
- `audio_supports_score`
- `audio_disagrees`
- `audio_ambiguous`
- `insufficient_signal`
- `analysis_unavailable`

Any suggested correction remains human-reviewable.

## Tests
Use legally redistributable synthetic/original fixtures covering:
- isolated bass;
- isolated guitar;
- chords/polyphony;
- bends;
- dense mixes;
- tempo changes;
- silence/noise;
- stem artifacts;
- intentional GP5/audio mismatches.

## Acceptance criteria
- External evidence cannot mutate canonical arrangements without an explicit application/review action.
- Every evidence item is traceable to input audio, stem, provider, model, and version.
- Failures degrade to unavailable evidence rather than invalid arrangement state.
- Bass, Lead, and Rhythm remain equally supported.
- Regression fixtures demonstrate measurable review/alignment value before enabling the pipeline by default.

## Rollback
Each provider remains optional behind an adapter. Disabling stem separation or transcription must leave the existing score-first workflow fully functional.