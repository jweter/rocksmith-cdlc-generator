# Reviewed Rocksmith XML Handoff

Issue #241 now has a read-only boundary between the promoted human-reviewed timing/authoring path and Rocksmith XML construction.

`reviewed_rocksmith_xml_input(project_dir, role)` normalizes Bass, Lead, or Rhythm into one provenance-bearing handoff model while preserving:

- the exact promoted reviewed start time and duration for every source event;
- confirmed string/fret positions and explicit tuning;
- source-event identity, imported confidence, and accepted trust class;
- recording, score, fan-out output, and source-track provenance;
- explicit human-reviewed Lead/Rhythm chord membership and its position-derived six-string shape.

## Fail-closed boundary

This adapter does not reinterpret musical evidence. In particular:

- notes that still require review or lack accepted source trust were already rejected by the reviewed Bass/Guitar authoring adapters;
- the handoff rejects technique labels that the current Rocksmith XML bridge cannot represent losslessly;
- it does not infer hammer-on/pull-off direction, bend curves, slide targets, chord names, left-hand fingering, anchors, hand shapes, tones, or Dynamic Difficulty;
- it does not generate or write XML, alter canonical charts or timing, package CDLC, modify a Rocksmith installation, or interact with NoCableLauncher.

The next XML-construction step can therefore consume reviewed facts without silently falling back to the older unreviewed timing/chart path. Actual XML emission remains behind the existing validation/review and packaging boundaries.

## Visibility of which timing path an export used

Which path an export actually took (promoted reviewed score-anchor timing vs. the older `charts/<role>_source.json` / `bass_mapped.json` path) was previously only discoverable by reading the free-text `assumptions` list inside `eof/export_manifest.json` or `eof/<arrangement>_export_manifest.json`. Both manifest models now also carry a structured `timing_source` field (`"reviewed_score_anchors"` or `"legacy_chart"`), and the desktop Rocksmith XML Export window reads it back after a successful export to label the per-arrangement status line (for example, "Exported (reviewed score-anchor timing): ..." vs. "Exported (legacy chart timing (no reviewed timing promoted)): ..."). This is read-only reporting of an already-made routing decision; it adds no new timing, mapping, or export authority.
