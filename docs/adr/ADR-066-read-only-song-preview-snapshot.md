# ADR-066: Read-only Song Preview Snapshot

## Status

Accepted

## Context

The Song Preview & Timing Editor should become the main human-review workspace, but GUI widgets should not parse imported-source files or reinterpret provenance themselves. ADR-063 through ADR-065 established a trusted MusicXML arrangement manifest as the project-level authority marker for an imported arrangement set.

The first editor-facing slice needs a stable, testable data contract before playback or timing mutation is introduced.

## Decision

1. Add a library-level `SongPreviewSnapshot` as a read-only projection of one trusted MusicXML arrangement manifest.
2. Expose the shared beat grid, tempo events, time signatures, arrangement metadata, normalized note events, confidence/trust state, and warnings needed by future GUI bindings.
3. Keep source/manifests/imported artifacts immutable while creating the snapshot.
4. Resolve every referenced file inside the project directory and reject path traversal or absolute paths outside the project.
5. Revalidate manifest-to-output provenance, source-part/role selection, tuning, and note count at read time.
6. Require all displayed arrangements to share one canonical beat/tempo/time-signature timebase.
7. Keep timing edits, waveform/playback, Qt integration, and automatic manifest discovery outside this slice.

## Consequences

The future desktop workspace can consume one validated display model rather than duplicating parsing and trust logic. Mixed or stale cached artifacts fail closed before they reach the UI. The implementation remains deterministic, lightweight, and testable on CI without audio hardware or GUI dependencies.
