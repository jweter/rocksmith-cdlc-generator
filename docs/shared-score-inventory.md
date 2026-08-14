# Shared score inventory

The project-level score contract can now be populated from a complete MusicXML/MXL or Guitar Pro 3-5 score before any arrangement-specific extraction occurs.

## Inventory behavior

`score_inventory` records every discovered symbolic track/part with:

- stable source track index;
- source track/part name;
- coarse instrument hint when available;
- low-string-first tuning when the source supplies tuning metadata;
- pitched note count.

The score bytes are hashed once and the resulting `ProjectScoreSource` references the one imported score path. Bass, Lead, and Rhythm are mappings into that shared inventory rather than three separate score ingests.

## Mapping proposals

The existing Guitar Pro and MusicXML arrangement-scoring rules are reused to propose Bass, Lead, and Rhythm mappings. Explicit role labels such as `Bass`, `Lead Guitar`, and `Rhythm Guitar` can produce exact-confidence proposals when they uniquely win their role. Weaker structural evidence produces lower-confidence proposals.

A proposal is not human confirmation. `human_confirmed` remains false for importer-created mappings.

If the best candidates tie, the inventory leaves that role unmapped instead of choosing a track arbitrarily. This preserves the ambiguity for a later CLI/GUI review step.

## Supported sources in this slice

- MusicXML: `.xml`, `.musicxml`, `.mxl`
- Guitar Pro through PyGuitarPro: `.gp3`, `.gp4`, `.gp5`

GPIF / modern Guitar Pro container support remains a separate adapter task; the persistent score contract already has a `gpif` format value but this inventory module does not claim to parse it yet.

## Next integration step

The next orchestration layer can register the inventory under the project, present proposed Bass/Lead/Rhythm mappings for confirmation when needed, and then fan confirmed tracks into the existing arrangement importers while sharing one recording/score synchronization model.
