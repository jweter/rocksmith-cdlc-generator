# ADR-004: Beat tracker strategy on Windows

## Context
The project targets Windows 11 and Python 3.12. The roadmap calls for benchmarking beat trackers before committing to one engine.

Essentia's RhythmExtractor2013 is an attractive reference implementation because it returns BPM, beat timestamps, and confidence, but the official Essentia documentation states that Python bindings are not currently supported on Windows. Making it a required V1 dependency would therefore add unnecessary build/toolchain friction on the target machine.

## Decision
Use a tracker adapter boundary and benchmark two local rhythm-analysis approaches that run cleanly in the Python 3.12 environment:

1. `librosa.beat.beat_track` as the initial dynamic-programming baseline.
2. `librosa.beat.plp` as a second predominant-local-pulse baseline.

Keep Essentia as a future optional/subprocess candidate rather than a core dependency.

## Alternatives
- Require Essentia and build/cross-compile its C++ stack for Windows.
- Commit immediately to only one beat tracker.
- Run beat analysis in a Linux/WSL service.

## Reasons
The chosen approach is local-first, easy to test in GitHub Actions, works with the core Python runtime, and preserves the roadmap requirement that the engine remain replaceable.

## Consequences
The first benchmark compares two algorithms from the same library rather than two unrelated packages. This is sufficient to validate the adapter and benchmark harness, but a later benchmark should add a genuinely independent implementation once a Windows-friendly candidate is selected.
