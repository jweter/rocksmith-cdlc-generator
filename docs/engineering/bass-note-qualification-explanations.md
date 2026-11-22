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

## Post-v6 source-signal veto (canonical #796 slice 28)

The per-event reason/threshold schema remains as described in v6, but
reconciliation **v7** adds an earlier production source gate:
`screen_bass_stem_obvious_negatives` must not find silence-only or
transient-only content in the hash-bound Bass stem, even when a transcriber
reports perfect self-confidence. A failed negative screen causes
`verified_stem_provenance=False` and thus `UNVERIFIED_STEM` on a
matching note. All previous currentness/provenance, content-clock and
non-identity requirements remain intact. A passing screen means only
"not obviously silent/percussive" and **never** proves Bass instrument identity,
source separation, musical accuracy, or actual gameplay. Old v6 chart
artifacts must be regenerated to inherit v7 semantics.

## Production matched-note octave veto (canonical #796 slice 31)

In addition to the diagnostic root-to-octave threshold, reconciliation
**v8** injects `inspect_bass_octave_leakage` into the actual source
promotion boundary. After v7 independently verified the stem hash,
recording clock, noncloned signal and percussion negative, this
step examines two non-overlapping 320-ms local PCM windows of an otherwise
strong matching note. A repeated octave-dominated signal at least 8x the
expected lower fundamental appends `OCTAVE_LEAKAGE_NEGATIVE` and keeps
`symbolic_unverified`; unreadable source adds
`OCTAVE_SCREEN_UNAVAILABLE`. Neither ambiguous/short observations nor
diagnostic plausibility are new positive Bass proof. Old v7 charts become
stale, and no real-song source truth, two-bar timing or gameplay PASS
is implied.

## Reconciliation v9: physically independent per-event onset

The previous v8 per-event authority relied on a self-reported transcriber
`timing_confidence`, in addition to independent stem/provenance and octave
negative controls. Version **9** requires another bounded PCM attack/onset
measurement from the currently verified local stem before an otherwise
qualified pitch-matched event can become `symbolic_verified`.
`NO_INDEPENDENT_ATTACK`, `INSUFFICIENT_ATTACK_EVIDENCE`,
`ATTACK_SCREEN_UNAVAILABLE`, or
`LOW_INDEPENDENT_ATTACK_CONFIDENCE` now keep a candidate review-required.
The event's measured 10ms-bin, 30ms local pre/post attack confidence
and onset delta are exposed as sanitized observations with exact
minimum confidence and maximum delay thresholds. This is *not*
independent Bass instrument/pitch/source-isolation evidence. Stale v8
artifacts must be regenerated. See
`docs/engineering/bass-attack-onset-independent-evidence.md`.
