# ADR-037 — Verified private PSARC extraction

## Status
Accepted

## Context
The local tone-reference library needs package metadata and arrangement artifacts from the user's installed Rocksmith DLC. The live installation is immutable input under ADR-035. Direct extraction from files beneath the Rocksmith installation would weaken that boundary and make accidental writes harder to rule out.

## Decision
Raw PSARC extraction for library analysis must consume only a `VerifiedPsarcCopy` produced by `local_psarc_workspace.py`.

The extraction path is:

1. Hash the live PSARC read-only.
2. Copy it into private, content-addressed storage outside the Rocksmith installation.
3. Verify the copy SHA-256 equals the live source SHA-256.
4. Re-hash the private copy immediately before extraction.
5. Extract only into the private workspace directory derived from that SHA-256.
6. Reject any bridge-reported artifact path that resolves outside that private extraction directory.

The Rocksmith2014.NET bridge exposes a generic `extract` command that unpacks the verified private copy without converting or modifying the source package.

The Python wrapper recursively examines extracted JSON only to identify files containing keys whose names include `tone`. This is candidate discovery, not semantic interpretation. Detailed normalization into `LocalToneReference` records is a later step and must retain provenance back to the verified source SHA-256.

## Consequences
- The live Rocksmith installation remains untouched.
- A changed or corrupted private copy cannot be analyzed under an old verification receipt.
- Package extraction can be cached by source SHA-256.
- Tone parsing can evolve independently from PSARC extraction.
- Extracted commercial content remains private local data and must never be committed or redistributed.
