# ADR-042: Controlled first local tone-corpus scan

## Status
Accepted

## Context
The private tone-reference pipeline can now stage verified PSARC copies, extract manifests, parse Tone2014 structures, index them incrementally, and explain corpus/reference statistics. The first scan against a real installed Rocksmith library should be deliberately small so parser or source-classification problems are visible before a large corpus is trusted.

The live installation at `C:\Program Files (x86)\Steam\steamapps\common\Rocksmith2014\dlc` remains immutable input.

## Decision
Add a first-scan orchestration boundary that:

- requires the DLC directory to be inside the configured Rocksmith installation;
- requires workspace and library outputs to be outside the live installation;
- caps a first scan at 25 packages, with 5 as the operator-command default;
- reuses the verified-copy, extraction, parser, and incremental-indexing pipeline rather than bypassing it;
- writes a private combined report containing package outcomes and post-scan corpus statistics;
- keeps source authority explicit through the existing operator-authored source map, defaulting to `unknown` when not classified.

## Consequences
A first real scan is bounded, inspectable, repeatable, and safe to abort. Failed packages remain isolated and retryable. The generated report and normalized corpus remain under ignored private storage and must not be committed.

This workflow does not make similarity evidence authoritative and does not weaken the human review gate for tone recommendations or package injection.
