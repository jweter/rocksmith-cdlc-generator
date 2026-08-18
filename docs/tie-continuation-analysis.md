# Tie continuation analysis

The Product Reality run that exposed a four-digit Arrangement Preview review queue also showed imported Guitar Pro `tie` events in the queue. Guitar Pro ties are often continuation notation rather than independent musical decisions, so treating every tie as an unrelated human-review task can create substantial review pressure.

`tie_continuation_analysis.py` adds a read-only classifier for one normalized imported source track. A tie is classified as an `exact_continuation` only when exactly one earlier event on the same physical string, fret, and MIDI pitch ends at the tie onset within a strict timing tolerance. Positionless, non-adjacent, orphaned, or multiply-matching ties remain `ambiguous_or_orphan`.

This slice intentionally does not fold tied notes, extend durations, clear `review_required`, mutate score fan-out, or change downstream authoring. It establishes the fail-closed evidence boundary required before a later importer/reconciliation change can safely normalize mechanically certain tie continuations while leaving ambiguous cases for human review.

The analysis is source-level and does not accept score mapping, source rights, timing alignment, fingering, chord identity, techniques beyond the explicit tie marker, tones, validation, or package readiness. It does not touch the live Rocksmith installation or NoCableLauncher and does not add commercial/private media or Ubisoft-derived content to the repository.
