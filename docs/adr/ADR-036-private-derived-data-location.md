# ADR-036 — Private Derived Tone Data Storage

## Status
Accepted

## Decision
Generated tone-reference libraries, extracted package metadata snapshots, and local scan plans belong under ignored local storage such as `private/` or `cache/`.

The repository may contain schemas, tests, synthetic fixtures, and extraction/indexing code, but must not contain commercial PSARC files, Ubisoft manifests, or a copied catalog derived from installed Rocksmith content.

This keeps the implementation reproducible while preserving the local-only data boundary.