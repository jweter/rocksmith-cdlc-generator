# Toolchain Decisions

Status: Milestone 0 working decisions

## Authoring bridge

V1 will target a Rocksmith/EOF-compatible intermediate export rather than implementing PSARC packaging from scratch. DLC Builder remains the downstream packaging and validation tool until a stable programmatic bridge is justified.

## Canonical working audio

The project preserves original source audio unchanged and derives a 44.1 kHz stereo 16-bit PCM WAV as the canonical analysis timeline.

## Core Python runtime

The core application targets Python 3.12. Audio ML engines may run behind adapters or subprocesses in separate environments when their dependency constraints differ.

## Bass-first transcription

Bass is the first automated arrangement target. Structured notation or isolated bass stems take precedence over full-mix transcription.

## Confidence-aware representation

Generated musical events must eventually retain provenance, component confidence values, and a review-required flag. Low-confidence predictions are surfaced for human review rather than silently accepted.

## Packaging boundary

No generated file is copied into the live Rocksmith installation automatically. Build artifacts go to a staging directory and installation remains an explicit user action.

## Next implementation target

1. Complete project ingest and normalization.
2. Add beat-tracker adapter interface.
3. Benchmark at least two beat trackers on legal/synthetic fixtures.
4. Emit `tempo_map.json` and `beats.csv`.
5. Add validation and a simple beat-grid review artifact before starting bass transcription.
