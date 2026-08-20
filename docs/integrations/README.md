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

## Planned integrations

| Project | Role | Boundary | Status |
|---|---|---|---|
| WhisperX | Speech/vocal timing and forced-alignment reference/provider | Isolated optional audio-analysis adapter | Evaluate narrowly |
| Basic Pitch | Audio-to-MIDI / note evidence | Optional `NoteEvidenceProvider` | High-priority evaluation |
| Demucs lineage / StemSplit | Stem separation | Optional `StemProvider` | Compare maintained implementations |
| librosa | Deterministic DSP primitives | Rocksmith-owned service wrapper | Evaluate direct dependency |
| demixer | End-to-end music-analysis architecture | Reference-only | Architecture study |

## Target evidence architecture

```text
human-confirmed score authority
          ^
          |
master audio -> stems -> independent audio evidence
                         |- note evidence
                         |- vocal evidence
                         |- deterministic DSP
                         `- confidence/review diagnostics
```

No external analysis provider may silently rewrite canonical arrangement state.
