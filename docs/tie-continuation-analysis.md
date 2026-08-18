# Tie continuation analysis

The Product Reality run that exposed a four-digit Arrangement Preview review queue also showed imported Guitar Pro `tie` events in the queue. Guitar Pro ties are often continuation notation rather than independent musical decisions, so treating every tie as an unrelated human-review task can create substantial review pressure.

`tie_continuation_analysis.py` classifies one normalized imported source track. A tie is an `exact_continuation` only when exactly one earlier event on the same physical string, fret, and MIDI pitch ends at the tie onset within a strict timing tolerance. Positionless, non-adjacent, orphaned, or multiply-matching ties remain `ambiguous_or_orphan`.

The score-fan-out preview now uses that evidence to remove one narrow class of redundant review pressure: an exact continuation whose imported event is still review-required and whose only technique is `tie`. The persisted source event is not edited; its `review_required` flag, technique list, timing, position, and duration remain unchanged. Only the Song Workspace preview read model marks that mechanically proven continuation as not requiring a human tie decision, so it no longer appears in next/previous review navigation.

This exemption deliberately fails closed. An exact continuation carrying any additional technique, such as a bend or slide, remains reviewable. Ambiguous/orphaned ties remain reviewable. The slice does not yet fold tied events, extend predecessor durations, rewrite source/fan-out artifacts, or change Rocksmith XML authoring semantics.

The analysis does not accept score mapping, source rights, timing alignment, fingering, chord identity, other techniques, tones, validation, or package readiness. It does not touch the live Rocksmith installation or NoCableLauncher and does not add commercial/private media or Ubisoft-derived content to the repository.
