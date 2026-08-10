# ADR-001: Canonical internal arrangement representation

## Context

The generator must eventually export to EOF/Rocksmith tooling without coupling transcription, mapping, validation, and review logic to one external authoring application.

## Decision

Use a versioned, tool-independent JSON/Pydantic representation as the canonical arrangement model. EOF XML, MIDI, MusicXML, and other formats are imports/exports around that model.

## Alternatives

- Make EOF XML/project files canonical.
- Make MIDI canonical.
- Generate PSARC structures directly.

## Reasons

A neutral representation can preserve provenance, component-level confidence, review flags, alternate fret mappings, model versions, and validation state more naturally than MIDI or EOF-specific structures.

## Consequences

The project must maintain explicit exporters and validators, but the core pipeline remains independently testable and resilient to EOF/DLC Builder changes.
