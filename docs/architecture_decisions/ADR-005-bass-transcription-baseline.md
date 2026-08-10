# ADR-005: Bass transcription baseline and model isolation

## Status
Accepted for Milestone 4 baseline.

## Context
The project needs a local, testable bass transcription path before adding heavier ML models or source-separation requirements. The core application targets Python 3.12 on Windows 11.

Spotify Basic Pitch remains a useful future benchmark, but its published compatible Python versions currently stop at Python 3.11. Source-separation engines also have larger model/runtime requirements than the core ingest and chart logic.

## Decision
Use librosa pYIN plus onset detection as the first native monophonic bass transcription baseline.

- pYIN provides frame-level fundamental-frequency estimates and voicing probabilities.
- onset detection provides event boundaries.
- the adapter converts those estimates into the canonical confidence-bearing `NoteEvent` representation.
- low-confidence events are marked `review_required` instead of being silently accepted.

Keep Basic Pitch behind a future subprocess/isolated-environment adapter rather than downgrading the core Python runtime.

Treat bass source separation as an optional upstream adapter. Direct bass stems and structured inputs should bypass separation entirely.

## Why
This gives CI a deterministic, CPU-friendly engine that can be measured against synthetic ground truth while preserving the architecture needed to compare stronger models later.

## Consequences
pYIN is not expected to solve polyphonic full-mix transcription by itself. Its purpose is to establish the event schema, confidence semantics, benchmark harness, CLI workflow, and quality gates. Full-mix songs will likely benefit from bass stem separation before transcription.
