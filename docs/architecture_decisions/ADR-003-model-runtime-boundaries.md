# ADR-003: Isolate ML/DSP engines from the core runtime

## Context

The core project targets Python 3.12. Promising audio-analysis and transcription tools may have different Python, native-library, GPU, or model constraints.

## Decision

Keep the core application on Python 3.12. Treat beat tracking, source separation, and transcription engines as adapters. An adapter may execute in-process or through a subprocess/separate environment as long as it returns the versioned internal result contract.

## Alternatives

- Downgrade the entire project to the oldest common Python version.
- Vendor and patch third-party ML projects into this repository.
- Couple the pipeline directly to one model stack.

## Reasons

This prevents stable ingestion, provenance, mapping, validation, review, and export code from becoming hostage to ML dependency conflicts.

## Consequences

Adapters need explicit contracts, engine/version capture, health checks, deterministic result serialization where possible, and clear failure boundaries.
