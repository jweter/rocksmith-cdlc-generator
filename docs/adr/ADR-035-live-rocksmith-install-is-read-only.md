# ADR-035 — Treat the live Rocksmith installation as immutable input

## Status
Accepted.

## Context
The local tone-reference library will inspect many installed Rocksmith 2014 `.psarc` packages. The user's live installation is valuable and should never become a working directory for extraction, temporary files, rewrites, renames, or repair attempts.

Known Windows installation in the current deployment:

`C:\Program Files (x86)\Steam\steamapps\common\Rocksmith2014`

with DLC under:

`C:\Program Files (x86)\Steam\steamapps\common\Rocksmith2014\dlc`

Paths are configurable; the safety policy is not.

## Decision
1. The configured Rocksmith installation is read-only input.
2. A `.psarc` selected for inspection is hashed in place, copied into project-private ignored storage, and hashed again.
3. Inspection/unpacking may proceed only when source and copy SHA-256 values match.
4. Extraction and temporary outputs are prohibited anywhere beneath the configured Rocksmith installation root.
5. Cached copies are content-addressed by SHA-256 and reused when still valid.
6. No scanner function modifies, deletes, renames, repairs, timestamps, or otherwise writes to source DLC.
7. The private workspace is never committed; repository `.gitignore` already excludes `private/`, `cache/`, and `*.psarc`.

## Consequences
This costs additional disk I/O and some temporary storage, but sharply lowers the risk of corrupting or altering an installed DLC library. Incremental scanning and content-addressed copies prevent unnecessary duplication on later runs.

## Next step
The PSARC tone-extraction bridge must accept only a `VerifiedPsarcCopy` or an equivalent verified-copy receipt as its extraction source. Direct extraction from the live DLC path is prohibited by design.
