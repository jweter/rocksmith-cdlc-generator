# ADR-063: Persist MusicXML Arrangement Import Manifest

## Status

Accepted

## Context

The explicit multi-arrangement MusicXML workflow can import human-selected Lead, Rhythm, and Bass parts, but the orchestration result previously existed only in command output. The upcoming preview/timing editor needs a durable project-local statement of which source part became each arrangement role without re-running heuristics.

## Decision

1. After all selected MusicXML arrangements import successfully, write one project-local manifest under `sources/imported/`.
2. Bind every arrangement role to the exact source part index, part id/name, tuning, pitched-note count, and normalized imported JSON path.
3. Bind the manifest to the source filename and SHA-256.
4. Store normalized output paths relative to the project directory so manifests remain portable and do not disclose the operator's private source-library path.
5. Keep human part selection authoritative; the manifest records a decision but never makes one.
6. Do not copy the MusicXML/Guitar Pro source into the repository or project automatically.

## Consequences

The preview/editor and later orchestration can consume one deterministic entry point for imported arrangements. Re-importing the same source and selections rewrites the same manifest path deterministically. Local source-library locations remain private.
