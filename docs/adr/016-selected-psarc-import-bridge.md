# ADR-016: Selected PSARC Import via a Pinned Rocksmith2014.NET Bridge

## Status

Accepted.

## Context

Milestone 8.5 requires existing custom Rocksmith arrangements to be usable as symbolic source material. PSARC and SNG decoding are specialized Rocksmith formats and are already implemented and integration-tested by Rocksmith2014.NET/DLC Builder. Reimplementing those formats in Python would duplicate mature logic and create a large compatibility/security surface.

The generator also has a strict safety boundary: it must not scan, modify, or rewrite the live Rocksmith installation. Import must be explicitly initiated against a user-selected package.

## Decision

Use an optional .NET 10 bridge pinned to Rocksmith2014.NET commit `b87c9a3afd31c40ade9685a9244e718e7581c0cb`.

The bridge:

1. accepts one explicitly supplied `.psarc` path and one temporary extraction directory;
2. calls `Rocksmith2014.DLCProject.PsarcImporter.import`;
3. allows the upstream importer to decode PSARC/SNG and reconstruct Rocksmith XML;
4. reports reconstructed Bass XML paths to the Python process as JSON.

The Python adapter then:

1. verifies the selected file has a PSARC header and records its SHA-256;
2. invokes the bridge in a temporary directory;
3. requires exactly one Bass arrangement;
4. converts the reconstructed highest-difficulty Bass XML into `ImportedSource`;
5. preserves explicit Rocksmith ebeat times, tuning, string/fret, timing, and directly recoverable single-note techniques;
6. deletes temporary extracted assets when import finishes;
7. stores only the neutral source artifact beneath `sources/imported/`.

The upstream repository is cloned into gitignored `.tools/Rocksmith2014.NET` by `scripts/bootstrap_psarc_bridge.ps1`; it is not vendored into this repository.

## Trust and safety rules

- The importer never crawls the Rocksmith DLC directory.
- The original PSARC is read-only and never replaced.
- Imported notes remain `symbolic_unverified` until reconciled against the project's audio.
- Song packs or ambiguous multiple-Bass imports are rejected.
- Chords/double-stops are warned and not flattened into fabricated single notes.
- Malformed/non-monotonic beat grids fail explicitly rather than being silently repaired.
- Commercial audio/package contents are never committed to the repository or retained by the temporary extraction path.

## Compatibility basis

Rocksmith2014.NET's `PsarcImporter.import` opens the package, derives the DLC key, decodes SNG files, reads manifest attributes, reconstructs arrangement XML, extracts associated project assets, and rejects packages containing more than one xblock. Its integration tests verify PC/Mac PSARC import and reconstructed arrangement files.

The pinned upstream DLCProject currently targets .NET 10, so the bridge bootstrap and Windows CI use the .NET 10 SDK.

## Consequences

### Positive

- Reuses a mature Rocksmith format implementation.
- Keeps Python focused on the project's neutral source/reconciliation layer.
- Gives existing custom arrangements precise beat-grid and fingering data.
- Makes the upstream dependency reproducible through an exact commit pin.
- Windows CI can prove the helper still builds.

### Negative

- PSARC import requires the optional .NET 10 SDK and one-time bridge bootstrap.
- The importer depends on a pinned upstream source tree rather than a standalone NuGet package.
- Current neutral Bass scope does not yet reconstruct Rocksmith chord templates/double-stops.

## Follow-up

After this bridge is proven in CI, run an end-to-end import against a locally owned custom PSARC, align/reconcile it with the matching audio, and measure editing time versus the audio-only path.
