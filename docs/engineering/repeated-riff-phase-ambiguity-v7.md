# Repeated-riff phase ambiguity and recording-clock proof (v7)

Tracking: #796 slice 47, #455, #612. This is a *negative guard* against
historically observed ~two-measure-late arrangement notes; it is not proof
that the entire current song extraction pipeline is fixed.

## The false-confidence path

A perfect tempo grid can fit many beat-offset hypotheses equally well.
A repeated eight-beat guitar/Bass phrase can also yield 100% apparent
onset matches when aligned both to its first occurrence and to the repeat
two measures later. Choosing the **earliest** matching riff is a useful
deterministic tie-breaker but does **not** prove that the earliest musical
occurrence corresponds to the imported complete score's first event.

Prior to this patch, the EOF-derived Guitar Pro beat phase solver chose
the earliest candidate and returned a high confidence derived only from
match fraction/MAE. That could make two equally supported phase offsets
appear to be one uniquely verified recording-clock mapping.

## Corrective behavior

- `solve_beat_phase` now records the number of *equivalently strongest*
  beat-index phase candidates: same matched onset count and mean onset
  error within a bounded margin (min(20ms, 20% of onset tolerance)).
- The earliest **near-best** solution is still selected for a stable
  visualization/mapping hypothesis. The code does not silently move
  arrangements or apply a free-floating seconds shift.
- When more than one near-best candidate exists, the stored
  `AlignmentReport` is marked `phase_ambiguous=true` with an explicit
  `REPEATED_PHASE_AMBIGUITY_REVIEW_REQUIRED` warning.
- The overall and **every local region** alignment confidence are capped
  at 0.59, below the Bass reconciliation's 0.70 automatic verification
  threshold. A pitch match from an otherwise verified Bass stem cannot
  overrule phase ambiguity.
- A shared Bass/Lead/Rhythm timing candidate carries the ambiguity marker,
  and shared-timeline promotion **refuses** it until an independently
  supported or explicitly confirmed single beat phase has replaced the
  ambiguous candidate. Confirming the *score role* alone does not confirm
  its absolute recording-clock timing.
- The generic automatic beat-grid starter also records periodic
  alternatives and caps its confidence, because periodic click intervals
  do not independently prove a unique absolute source-to-recording offset.
  An explicitly supplied beat phase remains authoritative to the extent
  of its separate owner/source proof and does not get an automatic cap.
- Persisted alignment method advances v6→v7. Old v6 alignment JSON can
  no longer validate as current v7 evidence without requalifying its
  phase. Current source/audio authority and later refinement gates are
  preserved.

## Reference and intentional divergence

Inspected `raynebc/editor-on-fire` `src/beat.c` and `src/beat.h`
(`eof_detect_tempo_map_corruption`, `eof_get_nearest_beat`) for
mature beat-grid consistency/nearest-beat semantics. EOF validates its
beat positions but an interval-consistent grid alone does not resolve
which occurrence of a duplicated riff was intended by an imported
Guitar Pro score. This project adds stricter automated ambiguity
qualification for unattended evidence; it does not copy EOF source.

## CI acceptance

Original synthetic independent tests cover: the early phrase at
7.13s with an **additional** phrase exactly two measures later, stable
early mapping plus explicit non-PASS phase classification; unique
phrase gets a unique phase and remains uncapped; uniform metronomic
intervals do not claim an unambiguous initial beat; an explicitly
selected beat index does not get spuriously penalized. The shared
audio/click grid and imported score are not modified.

No commercial song has been run and no Rocksmith game playability
was proven. A future real-song Product Reality acceptance still
requires independently verified first and later landmarks for Bass,
Lead and Rhythm, the Wwise/PSARC bridge and final gameplay.
