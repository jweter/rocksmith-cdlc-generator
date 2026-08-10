# ADR-006: MIDI export and optional source-separation boundary

Status: Accepted

## Context

Milestone 4 requires both `bass_raw.json` and `bass.mid`. The Bass MVP also needs to accept or generate an isolated bass stem before transcription when full-mix audio is the only source.

The project core targets Python 3.12 and should remain lightweight. Source-separation runtimes are substantially heavier than MIDI serialization and may change models, acceleration backends, or package versions independently of the core pipeline.

## Decision

1. Use Mido as the lightweight Standard MIDI File writer/reader dependency in the core project.
2. Emit `charts/bass.mid` from the canonical `BassTranscription` event list.
3. Preserve absolute onset/duration semantics when converting seconds to MIDI ticks.
4. Treat this MIDI as an intermediate symbolic artifact; fret/string mapping and Rocksmith-specific authoring remain later transformations.
5. Keep source separation behind a `BassStemSeparator` adapter.
6. Support the external `audio-separator` CLI as the first local separator implementation, but do not install its ML stack as a core dependency.
7. Require the user/developer to choose a bass-capable model explicitly until project benchmarks justify a default.
8. Prefer an explicit clean stem, then generated `stems/bass.wav`, then full-mix normalized audio for transcription.

## Rationale

Mido provides direct Standard MIDI File read/write support with a small dependency footprint and supports current Python versions. The optional Audio Separator project supports Python 3.10+, exposes Bass as a single-stem target, produces 44.1 kHz output, and can run CPU-only or with optional acceleration.

Keeping separation external prevents PyTorch/ONNX/model dependencies from destabilizing ingest, beat mapping, validation, MIDI export, or later deterministic fret mapping.

## Consequences

- Milestone 4 has a deterministic MIDI artifact that can be regression-tested in CI.
- Source separation can be benchmarked on the target Windows machine without burdening every CI run.
- Model choice remains explicit and provenance-friendly.
- A future separator or Basic Pitch environment can replace the adapter implementation without changing the canonical transcription schema.
