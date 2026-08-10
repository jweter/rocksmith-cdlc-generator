# ADR-025: Multi-arrangement DLC Builder packaging

## Context

Bass, Lead, and Rhythm now have separate import, authoring, validation, and Rocksmith XML export paths. The remaining packaging path still assumes that every project is Bass-only: DLC Builder generation emits one Bass arrangement, staging hashes only Bass XML, and downstream package readiness invokes the Bass validator unconditionally.

That prevents a validated Lead/Rhythm project from becoming one Rocksmith package and also makes a guitar-only project impossible to stage safely.

The pinned `Rocksmith2014.NET` DLC project model defines the instrumental arrangement enum values used by DLC Builder:

- Lead: `Name = 0`, `RouteMask = 1`;
- Rhythm: `Name = 2`, `RouteMask = 2`;
- Bass: `Name = 3`, `RouteMask = 4`.

## Decision

Add a configured-arrangement packaging gate driven by `ProjectManifest.arrangement_instruments`.

For every configured playable arrangement:

- Bass uses the existing Bass validation report;
- Lead/Rhythm use their arrangement-specific guitar validation reports;
- any configured FAIL blocks DLC Builder preparation, staging, launch, and PSARC registration;
- WARNING remains packageable but visible in the combined gate status.

Generalize DLC Builder project generation so a single `.rs2dlc` can contain any validated subset of Lead, Rhythm, and Bass. Each arrangement receives:

- its own XML path;
- its own six-string tuning-offset vector;
- the upstream DLC Builder `Name` and `RouteMask` values;
- a deterministic MasterID and PersistentID derived from source hash + arrangement role;
- `BaseTone = guitar` for Lead/Rhythm and `BaseTone = bass` for Bass.

Preserve the previous `xml_path` + `tuning_offsets` Bass-only `build_dlcbuilder_project()` call as a compatibility shortcut for existing callers and tests.

Generalize build staging so every supported instrumental XML referenced by the `.rs2dlc` file is resolved, existence-checked, and SHA-256 hashed rather than locating Bass only.

## Trust boundary

Packaging does not make an arrangement more trustworthy. It only combines arrangements that have already passed their own validation boundary.

The generator still does not silently install a built PSARC into Rocksmith. Staging and PSARC registration remain outside the live game directory.

## Consequences

- A project configured for Bass + Lead + Rhythm can now produce one DLC Builder project containing all three arrangements.
- Guitar-only projects are no longer forced through Bass validation.
- Missing exported XML for any configured arrangement is a hard preparation error with an explicit export command in the message.
- Build-readiness manifests now include hashes for every included instrumental XML.
- Future vocals/showlights support can extend the same project-level packaging model without changing the instrumental enum contract.
