# ADR-061: Inspect Guitar Pro MusicXML Exports Before Arrangement Import

## Status

Accepted

## Context

The repository already has functional Guitar Pro 3/4/5 and MusicXML importers, but Guitar Pro 8 libraries commonly contain multi-part scores where Lead, Rhythm, Bass, vocals, and other instruments coexist. Automatic role selection is intentionally conservative and can fail on ambiguous scores.

The operator also has a local Guitar Pro 8 library and can export MusicXML directly. A read-only inspection step is therefore more useful than adding a new native `.gp` dependency immediately.

## Decision

1. Add a read-only MusicXML inspection model and command.
2. Preserve source-order part indices so the reported index can be passed directly to `import-musicxml --part-index`.
3. Report track name, tuning, note/rest counts, measure count, MIDI programs, and Lead/Rhythm/Bass heuristic scores.
4. Treat role scores as suggestions only; explicit human selection remains authoritative when uncertain.
5. Keep local score files outside the repository and do not copy or redistribute commercial tab content.
6. Correct live-input wording so near-full-scale values below 1.0 are described as clipping risk rather than proven clipping.

## Consequences

A Guitar Pro 8 score can now follow a practical local workflow: export MusicXML, inspect parts, choose an arrangement, and import it into the existing neutral symbolic pipeline. Native Guitar Pro 8 parsing can be reconsidered later only if MusicXML export proves insufficient for important techniques or metadata.
