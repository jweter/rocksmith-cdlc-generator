# Project fretboard diagnostics

The project-owned fretboard candidate inventory can now be evaluated against the exact current Bass, Lead, or Rhythm fan-out for a CDLC project.

Use `cdlc-fretboard PROJECT --instrument bass` (or `lead` / `rhythm`) to print a provenance-bound JSON diagnostic. The command verifies the registered score bytes, human-confirmed role mapping, current score fan-out manifest, project-local fan-out output, source hash, track identity, and explicit tuning before enumerating pitch-correct string/fret candidates.

The output includes the serialized source-position classification added in schema v2: each event is `candidate`, `missing`, or `inconsistent`, with aggregate counts plus the full pitch-correct candidate set. `--max-fret` changes only the diagnostic search bound and never edits chart data.

This surface is deliberately read-only. It does not choose a preferred fingering, rewrite imported positions, accept reviewed positions, import Editor on Fire edits, weaken validation, or modify the live Rocksmith installation or NoCableLauncher. Human fingering/playability review remains authoritative.

For Product Reality issue #304, this diagnostic is intended to separate importer/tuning/string-fret defects from ordinary multi-position fingering ambiguity while the packaged Bass validation retest remains a separate human evidence lane.
