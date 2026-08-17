# Reviewed Lead/Rhythm authoring adapter

This adapter is the next bounded consumer step after reviewed guitar chord identity is preserved in the export projection.

It converts a `ReviewedExportArrangement` for Lead or Rhythm into a read-only authoring input while preserving:

- promoted human-reviewed timing;
- exact source-event identity;
- explicit six-string tuning;
- confirmed string/fret positions;
- note techniques and source trust metadata;
- explicit human-reviewed chord membership by source-event index;
- recording, score, and fan-out provenance hashes.

The adapter fails closed when a note still requires human review, source trust has not been accepted, a string/fret position is absent, the position is outside six-string guitar bounds, the position disagrees with pitch, or tuning is missing/invalid.

## Deliberate boundary

This layer does **not** infer chord membership, choose alternate chord fingerings, create Rocksmith chord templates, write Rocksmith XML, rewrite canonical charts or timing, select tones, package CDLC, or modify a live Rocksmith installation or NoCableLauncher.

Those steps remain downstream and must continue to respect the existing human review gates. In particular, chord identity and fingering are treated as reviewed source authority rather than reconstructed from note onset proximity.
