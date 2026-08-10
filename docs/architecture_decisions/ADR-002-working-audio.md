# ADR-002: Canonical working audio is 44.1 kHz PCM WAV

## Context

Source files may be WAV, FLAC, MP3, or M4A. Beat analysis, transcription, synchronization, EOF, and downstream Rocksmith tooling need a deterministic timeline.

## Decision

Preserve the original source unchanged. Generate a derived 44.1 kHz stereo, 16-bit PCM WAV for V1 analysis and synchronization.

## Alternatives

- 48 kHz working audio.
- Preserve each source codec throughout the pipeline.
- Mono-only working audio.

## Reasons

44.1 kHz aligns well with the Rocksmith authoring workflow and provides a stable derived format for hashing, caching, regression tests, and downstream DSP. Individual ML engines may resample internally when required.

## Consequences

All model timestamps must be converted back to the canonical project timeline before they enter the internal arrangement representation.
