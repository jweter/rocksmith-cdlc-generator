# Third-Party Integration Guide Index

Last reviewed: 2026-08-20

This directory records approved evaluation paths for external technology that may improve the Rocksmith CDLC Generator without weakening deterministic authoring, provenance, validation, or human review.

## Governing rules

- External tools provide signals or services; they do not become authority over arrangement state.
- Bass, Lead Guitar, and Rhythm Guitar remain equally first-class.
- Human-confirmed score/source mapping remains authoritative.
- Any probabilistic timing, transcription, detection, or alignment result must carry provenance and confidence/review state.
- External dependencies must be replaceable behind adapters.
- Do not copy upstream source code into this repository without a dedicated license/maintenance decision.
- Pin versions and re-run regression fixtures before upgrades.
- Never allow an external tool to bypass validation, stale-state invalidation, or packaging gates.

## Planned integration

| Project | Role | Boundary | Status |
|---|---|---|---|
| WhisperX | Speech/vocal timing and forced-alignment reference/provider | Isolated optional audio-analysis adapter | Evaluate narrowly |

WhisperX is not a guitar-note transcription engine. The project should borrow or use only capabilities that improve source-audio segmentation, vocal/lyric timing, timestamp handling, or alignment architecture where empirically useful.
