# Stereo waveform envelope semantics

Song Workspace waveform rendering is a review aid tied to the normalized project WAV. It must not visually erase audible content because stereo channels happen to have opposite polarity.

## Envelope rule

For each display bucket, the waveform cache inspects every PCM16 sample from every channel and stores the most negative and most positive normalized sample. It does **not** average signed channels before computing extrema.

This means a frame such as `(+0.8, -0.8)` remains visibly energetic instead of collapsing to zero, and a strong event present in only one channel remains visible.

## Cache compatibility

The waveform cache schema is version 2. Version 1 caches used signed channel averaging and are deliberately rejected/rebuilt even when the normalized audio SHA-256 is unchanged. This prevents stale visualization semantics from surviving the correctness fix.

## Authority and safety boundary

The envelope is visualization-only. It does not alter normalized audio, timing authority, score mappings, arrangement notes, techniques, tones, validation, export/package state, or installation behavior. No live Rocksmith installation or NoCableLauncher files are touched.
