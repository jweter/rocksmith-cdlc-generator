# ADR-019: Structural PSARC verification before installation

## Status

Accepted for Milestone 8 first-playable hardening.

## Context

The existing `register-psarc` staging step verifies only the PSARC header (`PSAR` magic and `zlib` compression marker), file size, and SHA-256. Those checks prove that a file resembles a PSARC archive but do not prove that Rocksmith2014.NET can open it or that the package contains the core resources required for a playable single-song Bass CDLC.

## Decision

Extend the pinned Rocksmith2014.NET bridge with a read-only `inspect` mode. Inspection opens the archive with `Rocksmith2014.PSARC.PSARC.OpenFile` and returns its manifest plus categorized package entries without extracting or modifying the archive.

A package passes the Milestone 8 structural gate only when it contains at least one of each of these categories:

- Bass SNG arrangement;
- manifest JSON;
- audio WEM;
- sound bank (`.bnk`);
- xblock;
- album-art DDS.

A first-playable single-song package must contain exactly one xblock. Song packs remain outside the current scope.

The resulting `build/staging/psarc_structure.json` records the package SHA-256, size, pinned upstream commit, archive entry count, categorized paths, PASS state, and the fact that the generator did not install the package.

## Safety boundary

Structural PASS means that the archive opens and contains the expected core resource classes. It does not prove gameplay correctness, chart quality, tone quality, audio loudness, licensing, or compatibility with every Rocksmith installation. Manual in-game testing remains required.

The verifier is read-only and never copies anything into the live Rocksmith directory.

## Consequences

- Corrupt or obviously incomplete packages can be rejected before manual installation.
- Verification uses the same pinned Rocksmith2014.NET implementation already compiled by Windows CI for PSARC import.
- The Windows bridge build is the compatibility test for the F# inspection code.
- A later phase may deepen checks by decoding the generated Bass SNG and cross-checking DLC key/manifest identity, but those checks are not required for this first structural gate.
