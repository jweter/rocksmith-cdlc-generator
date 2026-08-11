# ADR-040: Resumable local tone batch scanning

## Status

Accepted.

## Context

The project can safely index one installed Rocksmith PSARC at a time through the immutable-install boundary, SHA-256-verified private copies, private extraction, conservative tone parsing, and verified library ingestion. The user's installed DLC collection is large enough that a full scan must tolerate individual corrupt, unsupported, or otherwise problematic packages without losing prior progress or forcing a complete restart.

## Decision

Add an incremental batch scanner around the existing `changed_psarcs()` and one-package ingestion pipeline.

The scanner:

1. reads the current private tone-reference library when present;
2. plans only new or changed PSARCs using the existing path/size/mtime cache;
3. processes packages serially through the existing verified-copy ingestion boundary;
4. persists each successful package immediately, so later failures cannot erase progress;
5. catches failures only at the package boundary and records the exception type/message in a private batch report;
6. leaves failed packages unindexed so the next run naturally retries them;
7. supports a per-run package limit for controlled/resumable scans; and
8. never infers source authority from filenames or ambiguous package metadata. Authority comes from an operator-authored exact-path map, an explicitly supplied default, or remains `unknown`.

The source map is constrained to paths under the configured DLC root. Relative source-map entries are resolved beneath that root; escaping entries are rejected.

## Consequences

A large local collection can be indexed over multiple runs without rescanning successful unchanged packages. One malformed DLC package no longer blocks the rest of the corpus. Batch reports provide a durable private failure queue for later diagnosis.

This does not weaken any existing safety boundary: the live Rocksmith installation remains read-only, commercial DLC or extracted manifests are never committed, analysis operates on verified private copies, and source authority is not guessed.

## Next

After CI passes, run the scanner against a small controlled subset of the real local DLC folder, inspect the private batch report and normalized records, then add library-level corpus statistics and reference-search diagnostics before using the corpus in automatic tone recommendation.
