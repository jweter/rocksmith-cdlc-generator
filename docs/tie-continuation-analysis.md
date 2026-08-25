# Tie continuation analysis

The Product Reality run that exposed a four-digit Arrangement Preview review queue also showed imported Guitar Pro `tie` events in the queue. Guitar Pro ties are often continuation notation rather than independent musical decisions, so treating every tie as an unrelated human-review task can create substantial review pressure.

`tie_continuation_analysis.py` classifies one normalized imported source track. A tie is an `exact_continuation` only when exactly one earlier event on the same physical string, fret, and MIDI pitch ends at the tie onset within a strict timing tolerance. Positionless, non-adjacent, orphaned, or multiply-matching ties remain `ambiguous_or_orphan`.

The score-fan-out preview now uses that evidence to remove one narrow class of redundant review pressure: an exact continuation whose imported event is still review-required and whose only technique is `tie`. The persisted source event is not edited; its `review_required` flag, technique list, timing, position, and duration remain unchanged. Only the Song Workspace preview read model marks that mechanically proven continuation as not requiring a human tie decision, so it no longer appears in next/previous review navigation.

This exemption deliberately fails closed. An exact continuation carrying any additional technique, such as a bend or slide, remains reviewable. Ambiguous/orphaned ties remain reviewable. The slice does not yet fold tied events, extend predecessor durations, rewrite source/fan-out artifacts, or change Rocksmith XML authoring semantics.

## Exact folding at the reviewed authoring boundary

The reviewed Bass/Lead/Rhythm authoring adapters now consume the same conservative
classification to fold a mechanically exact tie chain into its primary note before
the Rocksmith XML handoff. Folding is allowed only when:

- `tie` is the continuation event's only technique;
- the source and promoted reviewed clocks are both exactly adjacent (within the
  existing floating-point tolerance);
- string, fret, and MIDI pitch are unchanged;
- exactly one preceding authoring note can own the continuation; and
- the continuation independently passes accepted-source-trust, physical-position,
  and pitch checks.

The primary note receives the full reviewed duration and keeps the continuation
source-event indexes as additive lineage. The redundant continuation note head and
its unsupported `tie` label do not reach XML. Exact repeated guitar tie chords are
deduplicated only when their mapped primary chord identity was already explicitly
reviewed.

This rule deliberately does not bridge a source or reviewed timing gap, resolve an
overlap, move a tie between strings/frets, accept a tie carrying another technique,
or infer a mixed continuation chord. Those cases continue to fail closed through the
existing human-review or unsupported-technique gates.

Reference behavior was inspected in current `raynebc/editor-on-fire`
`src/gp_import.c` at upstream `98753f56ec655e86bd1d753d4e1e30002a94e151`,
including the multi-string tie extension correction in
`55b6a01896870454dabef588571386842ad8abe0` and current different-string handling
after `52268943ad5731c3a567c1c40d605ee3d8bd98b1`. No EOF source code is copied;
the Python plan is a narrower adaptation that retains this project's stronger
review/provenance boundaries.

The analysis and fold do not accept score mapping, source rights, timing alignment,
fingering, new chord identity, other techniques, tones, validation, or package
readiness. They do not touch the live Rocksmith installation or NoCableLauncher and
do not add commercial/private media or Ubisoft-derived content to the repository.
