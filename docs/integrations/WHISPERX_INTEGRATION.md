# WhisperX Integration Plan

Last reviewed: 2026-08-20
Upstream: `m-bain/whisperX`
Integration posture: **Optional, narrow audio-analysis provider and architectural reference**

## Purpose

WhisperX provides time-accurate speech transcription, forced alignment, word-level timestamps, VAD, and diarization. Those capabilities can improve Rocksmith workflows that need lyric/vocal timing, section cues, timestamp normalization, or an additional temporal reference against the recording.

WhisperX is **not** a guitar or bass note-transcription engine and must never be used as if speech timestamps establish note authority.

## License gate

WhisperX is currently BSD-2-Clause. Redistribution is generally permissive provided its copyright/license notice requirements are retained. Its transitive dependencies and downloaded speech/alignment/diarization models have their own licenses and access terms; those must be reviewed separately before packaging or commercial distribution.

Before implementation:

- pin the WhisperX version;
- list all required models and their licenses;
- identify whether Hugging Face or other credentials are required;
- confirm whether model files may be redistributed or must be downloaded separately;
- record GPU/CPU requirements and supported Python versions;
- add third-party notices where required.

## Allowed use cases

Initial evaluation may cover:

1. lyric/vocal word timestamps for songs where lyrics are available or generated;
2. voice/non-voice segmentation as an auxiliary song-structure signal;
3. timestamp normalization and forced-alignment design patterns;
4. optional cue generation for manual review/navigation;
5. benchmark/reference implementation for coarse-to-fine temporal alignment architecture.

## Explicitly disallowed assumptions

- A WhisperX word boundary is not a guitar/bass note boundary.
- Vocal timing must not overwrite score-to-recording alignment.
- Absence of detected speech must not imply an instrumental section is musically empty.
- Diarization labels must not be treated as canonical performer identities without human verification.
- WhisperX results must never bypass arrangement review or packaging gates.

## Target architecture

```text
source audio
  -> existing project audio identity/hash
  -> optional WhisperXAnalysisProvider
      -> VAD / transcript / forced alignment
  -> normalized AuxiliaryTimingEvidence
  -> review/visualization/optional alignment features

score/tab authority -------------------------------> arrangement pipeline
recording alignment authority --------------------> arrangement pipeline
```

WhisperX-specific objects must terminate at the provider boundary. The application should own a small normalized schema such as:

- `start_seconds`;
- `end_seconds`;
- `text`;
- `confidence` when available;
- `speaker_label` when available;
- `provider`;
- `provider_version`;
- `model_id`;
- `audio_hash`;
- `analysis_timestamp`.

## Phased implementation

### Phase 0 - Define questions first

Select concrete questions the tool might answer, for example:

- Can lyric timestamps improve navigation during arrangement review?
- Can VAD/word timing provide useful section anchors without distorting musical timing?
- Is a speech-alignment-derived cue useful for validation against known lyric timestamps?

Do not integrate WhisperX merely because it produces rich timestamps.

### Phase 1 - Offline experiment

Use a small legally usable local benchmark set representing:

- clean vocals;
- dense metal mixes;
- instrumental passages;
- screamed/growled vocals;
- overlapping/backing vocals;
- long intros/outros.

Capture runtime, model size, GPU/CPU needs, timestamp stability, and obvious failure modes.

### Phase 2 - Provider adapter

Implement an optional provider that:

- accepts a project audio file/hash;
- runs outside canonical arrangement state;
- returns normalized auxiliary timing evidence;
- records model/version provenance;
- supports cancellation/timeouts;
- reports failures without blocking normal authoring.

### Phase 3 - UX experiment

Expose WhisperX output only in a clearly auxiliary surface, such as lyric timing/cue tracks or diagnostics. It must be visually distinguishable from score timing and arrangement-note authority.

### Phase 4 - Comparative validation

Measure whether the feature reduces review effort or improves navigation/alignment diagnostics. If it adds noise, dependency weight, or user confusion without measurable benefit, remove it.

### Phase 5 - Production hardening if retained

Add:

- deterministic version/model configuration;
- local model-cache handling;
- explicit download/setup flow;
- regression fixtures;
- stale-state invalidation when audio changes;
- provenance persistence;
- dependency/model license notices;
- graceful operation when WhisperX is not installed.

## Acceptance criteria

WhisperX may become a supported optional capability only if:

- it solves a documented user problem;
- results remain auxiliary evidence;
- score/audio authority rules remain unchanged;
- audio changes invalidate the analysis correctly;
- model and package licenses are acceptable;
- the packaged Windows application can function without it;
- failures do not block normal song authoring;
- UI clearly communicates the source and uncertainty of the result.

## Non-goals

- general instrument transcription;
- replacing the project timing model;
- automatic creation of authoritative Rocksmith notes from speech timestamps;
- hidden cloud processing;
- packaging model weights before license review;
- adding a large ML dependency to the default Windows build without evidence it is worth the cost.

## Rollback

WhisperX must be feature-gated. Removing/disabling it should delete or ignore only auxiliary derived analysis; canonical score mappings, timing, arrangements, validation, and package generation remain intact.

## Agent rule

Future agents must preserve the distinction between **auxiliary temporal evidence** and **authoritative musical timing**. No agent may use WhisperX output to silently mutate arrangement notes or declare a project ready.
