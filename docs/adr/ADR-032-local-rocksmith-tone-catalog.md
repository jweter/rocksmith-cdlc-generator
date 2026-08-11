# ADR-032: Derive the Rocksmith tone catalog locally

## Status

Accepted.

## Context

The tone-research and tone-family mapping pipeline can identify likely amp/effect families, but exact Rocksmith 2014 tone objects require valid device keys and knob definitions.

The authoritative Rocksmith Custom Song Toolkit models a tone as a `Tone2014` object with a `Gear2014` signal chain containing Amp, Cabinet, four pre-pedal slots, four post-pedal slots, and four rack slots. Individual devices are represented by `Pedal2014` entries containing a Rocksmith key, type/category, skin metadata, and knob values.

The Toolkit's own `pedalgen` utility generates `pedals2014.json` from Rocksmith 2014 gear manifests extracted from the user's game data. The full catalog therefore originates from Ubisoft game assets rather than from a public, independently authored constant table.

## Decision

The generator will not redistribute a copied Rocksmith 2014 device catalog or gear manifests.

Instead it will:

1. Accept a `pedals2014.json` generated locally from the user's own Rocksmith 2014 installation using the upstream Toolkit-compatible process.
2. Normalize that file into a schema-versioned catalog containing device names, types, categories, keys, bass applicability, skins, and knob definitions.
3. Record the SHA-256 of the source catalog for provenance and reproducibility.
4. Bind abstract researched component families to real local Rocksmith device keys deterministically.
5. Keep all catalog bindings human-review gated. Default knob values from the game catalog are valid device defaults, not claims that they reproduce the historical recording rig.
6. Leave automatic `.rs2dlc` tone injection disabled until the binding and parameter-selection layers are validated against real packages.

## Upstream evidence

Pinned reference commit: `2afa730c71cbacdee57dcf5cb6461f65eaf4f1e5` from `rscustom/rocksmith-custom-song-toolkit`.

Relevant upstream files:

- `RocksmithToolkitLib/DLCPackage/Manifest2014/Tone/Tone2014.cs`
- `RocksmithToolkitLib/DLCPackage/Manifest2014/Tone/Gear2014.cs`
- `RocksmithToolkitLib/DLCPackage/Manifest2014/Tone/Pedal2014.cs`
- `RocksmithToolkitLib/ToolkitTone/ToolkitPedal.cs`
- `RocksmithToolkitCLI/pedalgen/Program.cs`

## Consequences

This approach preserves compatibility with the user's installed Rocksmith version without committing copyrighted game-derived catalog data to the repository. It also gives tone decisions the same provenance discipline as audio, charts, build inputs, and PSARC receipts.

A later bridge may automate reading `gears.psarc` directly from the user's local installation, but that bridge must remain read-only and must not modify the live Rocksmith directory.
