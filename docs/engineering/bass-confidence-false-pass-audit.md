# Confidence-only false-PASS audit for Bass source comparisons

Tracking: #796 slice 34, #787 and #612 (Product Reality).

## Root cause

An audio transcription with the correct score pitch and onset, and with high
self-reported pYIN confidence, can appear to have a perfect note F1 even when
it comes entirely from the **unseparated original full mix**. Such a score is
a musical benchmark comparison, not independent evidence of Bass isolation.

An earlier comparator also accepted a WAV named `stems/bass.wav` as a ready
instrument source when its receipt hashes and recording clock matched the
master WAV. A byte-for-byte full-mix copy can satisfy both properties without
containing an actual Bass isolate. The separate reconciliation v5 clone guard
already refused such a source for note trust; this patch applies the
same negative control to **benchmark execution**, avoiding an inconsistent
side path that could output a misleading high confidence-only score.

## Implementation

The existing `cdlc-bass-evidence-compare` synthetic-known-truth scorer now:

1. Checks **actual PCM content distinctness** for a hash-receipted, clock-
   aligned Bass WAV. Exact copies, gain/polarity equivalents, insufficient
   evidence or corrupt audio report `UNQUALIFIED_SOURCE_IDENTITY` and are
   **not transcribed** as a stem source.
2. Keeps existing reference/prediction pitch/onset benchmark metrics for
   the original and frequency-focused sources. The historical
   `qualified_f1` field is explicitly a **confidence-only proxy**,
   not a trusted independent-source F1.
3. Records `naive_would_pass_count` (self-confident note candidates),
   `naive_truth_match_count` (how many of those coincide with the independent
   synthetic ground-truth notes), and `naive_false_positive_count`.
   These are **per evaluated source**, not independent new songs. Totals
   across source evaluations do not de-duplicate repeated notes.
4. Adds `confidence_only_false_pass_audit`: a warning whenever any
   high-confidence note could be incorrectly promoted from an unverified
   source. A perfect `qualified_f1=1.0` from the master mix still yields
   `independently_verified_note_count=0`,
   `independent_verified_f1=null` and `musical_acceptance=NOT_PROVEN`.
5. Retains resource admission, optional execution, exact source SHA-256,
   private report boundary and no model-download/no-write authority.

## Reproducible false-positive control

A tiny fake-transcriber regression deliberately returns all known-truth
Bass notes at perfect pitch/onset with high confidence **from the entire
original mixture**. The legacy confidence proxy reports F1=1.0, but the
false-pass report records the matching candidates as unverified, and zero
independently verified note authority. A perfect-clock, valid-receipt
clone stem is refused before pYIN is invoked. A separate readiness test
proves no diagnostic counts are invented without running a transcriber.

This rejects one class of false authority without denying the utility of
confidence-only comparisons for model selection.

## Limitations

Non-identical source PCM is necessary but not sufficient to prove an
isolated Bass. An EQ-filtered or deliberately modified full mix can pass
a non-identity test while still carrying all other instruments. No real
separator model was installed or executed, no private songs were uploaded,
no actual game timing was tested and no confidence threshold was relaxed.
A legitimate independent Bass evidence authority requires the full
source-separation/model and source truth gates before automatic
`symbolic_verified` promotion.
