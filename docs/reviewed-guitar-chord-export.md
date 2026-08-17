# Reviewed guitar chord identity in export projection

The reviewed export projection is the read-only boundary between promoted human-reviewed timing/source evidence and downstream authoring consumers.

For Lead and Rhythm, that projection must not flatten a reviewed chord into unrelated note events. `reviewed_export_arrangement(...)` therefore carries explicit human-reviewed chord membership alongside the individually projected notes.

## Contract

- Each chord group contains the exact source-event indices accepted by the reviewed chord layer.
- Chord membership is loaded against the current registered score, fan-out manifest, source track, and source-event identities.
- Bass carries no guitar chord groups.
- A chord may reference only source events present in the projected arrangement.
- One source event may belong to at most one reviewed chord group.
- Stale chord review authority fails closed instead of silently falling back to automatic onset grouping.
- Individual note timing, duration, pitch, string/fret evidence, technique evidence, source trust, and review flags remain unchanged.

## Scope boundary

This slice preserves chord identity for the next Lead/Rhythm authoring adapter. It does **not** convert chord groups into Rocksmith chord templates, infer missing chord membership, invent fingering, rewrite canonical charts, write Rocksmith XML, package CDLC, or modify a live Rocksmith installation or NoCableLauncher.

Human review remains authoritative for uncertain chord identity, fingering/playability, timing, source acceptance, tone, and package readiness.
