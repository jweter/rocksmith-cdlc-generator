# Explainable Bass note trust decisions (reconciliation v6)

## Problem

An event could be tagged `verified_match` because score MIDI pitch and a
nearby pYIN event matched, yet still remain `symbolic_unverified` and
`review_required` because the audio stem was unqualified, its independent
pitch/timing confidence was poor, or the score alignment was ambiguous.
Showing only `verified_match` hides why a note is not trusted and can
mislead an operator or unattended Product Reality classifier.

## New machine-readable evidence

Every `ReconciledBassNote` in `charts/bass_reconciled.json` includes:

- `qualification_reasons`: stable ordered codes; `QUALIFIED` only when
  all current independent trust conditions are satisfied. Otherwise,
  `UNVERIFIED_STEM`, `ONSET_OUTSIDE_VERIFIED_TOLERANCE`,
  `LOW_AUDIO_CONFIDENCE`, `LOW_PITCH_CONFIDENCE`,
  `LOW_TIMING_CONFIDENCE`, `LOW_ALIGNMENT_CONFIDENCE`,
  `AUDIO_REVIEW_REQUIRED`, `PITCH_CONFLICT`, `NO_AUDIO_ONSET`,
  or `NO_SYMBOLIC_MATCH`.
- `qualification_observations`: exact measured onset delta, overall/pitch/
  timing/alignment confidence and whether verified-stem provenance and
  source review were present, where available. No media or identifying
  file paths are included.
- `qualification_thresholds`: the exact minimum confidence/onset maximum
  compared with those values at the time of reconciliation.

These fields are derived from **the existing gate itself**, not a new
scoring model or an invitation to lower confidence thresholds. Existing
source trust and `review_required` semantics remain unchanged.
A pitch match is still an *observational match*, not necessarily trusted.

Persisted v5 and older reconciled charts become stale under version v6
because old files did not include the explanation fields; regeneration
must use the current source hashes and model provenance.

## Tests and limitations

Pure synthetic tests exercise all independent failure reasons simultaneously,
exact threshold-boundary behavior, verified-stem versus full-mix difference,
pitch conflicts, unmatched symbolic/audio notes, and stale legacy charts.

This supplies evidence for diagnosing the current zero-qualified Bass note
blocker without changing the playable arrangement, beat grid, cached audio,
human review authority or Rocksmith installation. It does **not** prove a
stem is actually isolated, detect correct fretboard fingerings, solve the
historic two-bar score shift or complete the UI display of these reasons.

Tracking: #796 slice 33; #787 and #612.
