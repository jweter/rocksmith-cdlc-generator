# ADR-065: Invalidate MusicXML Manifest Before Re-import

## Status

Accepted

## Context

ADR-063 introduced a durable MusicXML arrangement manifest, and ADR-064 verifies that imported arrangement artifacts still match the inspected source before publishing that manifest. A remaining transactional risk exists when a project already has a valid manifest for a source snapshot: a later re-import can overwrite one of the normalized arrangement JSON files and then fail before a replacement manifest is published. Leaving the old manifest in place would make it falsely authoritative for an output file that may no longer match its recorded part selection.

## Decision

1. Treat the project-level MusicXML arrangement manifest as the authority marker for the normalized arrangement set.
2. After validating requested roles/part indexes and identifying the source snapshot, remove any existing manifest for that same source SHA before starting fallible re-import writes.
3. Publish a replacement manifest only after every imported arrangement passes provenance/selection validation and the source SHA is re-verified.
4. If re-import fails, partial normalized arrangement files may remain, but no manifest may remain that claims they are authoritative.
5. Invalid requests that fail before re-import begins do not invalidate an existing manifest.

## Consequences

A failed re-import cannot leave an older manifest pointing at newly overwritten or partially updated arrangement outputs. The upcoming Song Preview & Timing Editor can use manifest presence as a stronger fail-closed authority signal.