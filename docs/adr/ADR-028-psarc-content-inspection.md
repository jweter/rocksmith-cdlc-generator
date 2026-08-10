# ADR-028: PSARC content inspection before manual installation

## Status

Accepted

## Date

2026-08-10

## Context

The generator can now produce a multi-arrangement DLC Builder project, stage and hash its inputs, launch DLC Builder, and register a returned PC PSARC with an auditable receipt. Registration verifies the PSARC header and proves that the generator-approved `.rs2dlc`, XML, audio, preview, and artwork inputs did not change after staging.

That evidence is necessary but not sufficient for installation. A file can have a valid PSARC header while still missing a configured arrangement or another required Rocksmith package asset.

The repository already pins `Rocksmith2014.NET` at commit `b87c9a3afd31c40ade9685a9244e718e7581c0cb` and includes a bridge capable of opening a PSARC and enumerating its manifest.

## Decision

Generalize the bridge inspection command to identify Lead, Rhythm, and Bass SNG entries independently while retaining the existing Bass extraction/import behavior.

Add a Python inspection boundary that consumes bridge JSON and validates a built package against the project configuration.

For every configured playable arrangement, the PSARC must contain at least one corresponding SNG entry. A package must also contain:

- exactly one xblock;
- at least one manifest JSON;
- at least one WEM audio file;
- at least one BNK sound bank;
- at least one album-art DDS;
- a non-empty PSARC manifest.

When the bridge is available during `register-psarc`, registration performs this inspection on the staged PSARC copy. Any failed content requirement blocks registration.

If the bridge is not available, registration may still write a provenance/header receipt, but the receipt records `content_inspection_status = NOT_RUN` and `safe_for_manual_installation = false`.

Only a receipt with `content_inspection_status = PASS` may set `safe_for_manual_installation = true`.

## Trust boundary

A passing content inspection proves that the produced archive can be opened by the pinned Rocksmith PSARC implementation and that expected high-level package components are present. It does not prove musical correctness, gameplay correctness, tone quality, difficulty quality, or that Rocksmith will accept every semantic detail.

The generator still never copies a PSARC into the live Rocksmith installation automatically. Installation remains an explicit human action after receipt review.

## Consequences

- The first real multi-arrangement package test will produce stronger evidence than a header-only check.
- Missing Lead/Rhythm/Bass SNGs are detected before installation when those arrangements are configured.
- Existing Bass PSARC import remains unchanged.
- Windows CI continues compiling the bridge, so changes to the F# inspection surface are checked with the repository's existing bridge bootstrap.
- Future deeper checks can inspect manifest attributes, SNG metadata, tones, and arrangement identities without changing the receipt trust model.
