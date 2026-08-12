# ADR-062: Explicit Multi-Arrangement MusicXML Import

## Status

Accepted

## Context

Guitar Pro 8 MusicXML exports may contain multiple guitar and bass parts. The repository can already inspect those parts and import one arrangement at a time, but a real-song workflow benefits from importing the explicitly chosen Lead, Rhythm, and Bass parts together.

Automatic role inference is useful for inspection but is not sufficiently authoritative to silently assign arrangements when multiple guitar parts are present.

## Decision

1. Add a multi-arrangement orchestration layer over the existing MusicXML importer.
2. Require explicit part indexes for every requested Lead, Rhythm, or Bass arrangement.
3. Reject duplicate role selections and reject assigning the same MusicXML part to multiple Rocksmith roles.
4. Validate all selected part indexes before writing any output.
5. Preserve the original MusicXML file in place and write only normalized project artifacts.
6. Keep human part selection authoritative when inspection scores are ambiguous.

## Consequences

A Guitar Pro 8 score can now move from inspection to project-ready Lead/Rhythm/Bass source artifacts with one command, while retaining the existing provenance, review, and safety boundaries. This makes the real-song path faster without weakening human review or introducing a new parser dependency.
