# Reviewed Rocksmith XML render boundary

This slice connects the provenance-bearing `ReviewedRocksmithXmlInput` handoff to the existing in-memory Rocksmith XML builders.

## What it does

- Bass reviewed notes are adapted to `BassMapping` without remapping pitch or choosing alternate positions.
- Lead/Rhythm reviewed notes are adapted to `GuitarAuthoringChart` while preserving explicit reviewed chord membership and preventing chord members from being emitted again as single notes.
- Repeated guitar chord shapes receive deterministic template IDs derived only from the reviewed shapes already present in the handoff.
- Timing, tuning, string/fret positions, techniques, source trust, and reviewed chord shapes are preserved.
- `build_reviewed_rocksmith_xml(...)` returns an in-memory XML element through the existing Rocksmith XML builder.

## Safety boundary

This module does **not** write XML files, mutate canonical chart or timing artifacts, infer missing chord identity/fingering, choose tones, package CDLC, install PSARCs, modify the live Rocksmith installation, or interact with NoCableLauncher.

The upstream reviewed handoff remains authoritative. Unsupported technique semantics continue to fail closed before this adapter is reached. Human source, timing, fingering/chord, tone, and package-readiness gates remain explicit.

## Next integration step

A later bounded slice may route the desktop XML export command through this reviewed in-memory builder, but only after preserving the existing export-readiness checks and private/generated-data boundaries.
