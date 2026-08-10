# ADR-010: DLC Builder project handoff

## Context

The generator can now emit a validation-gated Rocksmith 2014 Bass XML arrangement. Producing a playable `.psarc` also requires audio conversion, SNG generation, manifests, package assembly, and other Rocksmith-specific processing already implemented by DLC Builder / Rocksmith2014.NET.

## Decision

Generate a DLC Builder `.rs2dlc` project and hand packaging to DLC Builder rather than reimplementing SNG/PSARC generation in Python.

The bridge follows the current Rocksmith2014.NET `DLCProject` serialization contract:

- project format version `1`;
- relative file paths resolved from the `.rs2dlc` location;
- Bass arrangement `Name = 3` and `RouteMask = 4`;
- six-element Rocksmith tuning-offset array;
- `BaseTone = "bass"` with no invented tone definition;
- stable `MasterID` and `PersistentID` derived from source SHA-256 and arrangement identity.

Album, year, artwork, and preview audio must be supplied explicitly. The generator does not fabricate missing metadata or artwork.

## Consequences

- DLC Builder remains responsible for Wwise/WEM, SNG, manifest, and PSARC construction.
- The Python core remains smaller and easier to validate.
- A repeated export of the same source arrangement preserves arrangement identity.
- The `.rs2dlc` file can reference existing project audio/XML using relative paths, avoiding another full-song audio copy.
- Final playable-CDLC testing remains a separate milestone and must occur in staging before anything is copied into the live Rocksmith installation.
