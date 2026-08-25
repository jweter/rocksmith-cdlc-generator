# Source Timing Qualification Gate

Related: #304, #397

## Why this exists

A Guitar Pro or MusicXML file can be structurally valid, contain the correct notes, and still represent a different edit/version/count-in timeline than the recording used for the CDLC project. Product Reality testing exposed exactly this ambiguity: one score source appeared about 9-10 seconds late in the application, while a newly checked GP3 aligns to the recording in EOF for Bass.

The generator must therefore distinguish two questions before a score becomes song-level timing authority:

1. Is the score structurally usable?
2. Does the current score-to-recording timing candidate agree with independent recording evidence?

A valid parser result answers only the first question.

## Gate behavior

`source_timing_qualification.py` compares the authoritative score Bass track against the already-generated audio-derived Bass transcription after applying the current shared-timing candidate.

The comparison is intentionally conservative:

- only strong audio onset + pitch evidence is considered;
- candidate offsets are proposed only from equal-pitch score/audio pairs;
- offsets are bucketed and ranked so a single accidental onset cannot dominate;
- each hypothesis is scored with one-to-one repeated equal-pitch onset matches;
- a large non-zero offset blocks promotion only when it has repeated support, materially improves over the current timing, and clearly beats the next-best hypothesis;
- weak or ambiguous evidence is recorded as `insufficient_evidence` and does not invent a correction;
- no offset is ever applied by the qualification gate.

The evidence record is written to:

`analysis/source_timing_qualification.json`

Possible states are:

- `pass` — repeated evidence supports the current score-to-recording translation;
- `review_required` — repeated evidence strongly prefers a materially different translation, so shared timing promotion is blocked;
- `insufficient_evidence` — evidence is too sparse or ambiguous for an automatic judgment, so the existing human timing-review gate remains authoritative.

## Promotion boundary

`promote_shared_timeline()` now runs this qualification immediately before persisting `analysis/shared_timeline.json`.

Only `review_required` blocks promotion. The error explicitly tells the user that the likely causes include a wrong score/version or incorrect alignment and states that no automatic correction was applied.

This preserves human authority while preventing a strongly mismatched score from silently becoming the timing source for Bass, Lead, and Rhythm.

## Regression contract

Tests cover three cases:

1. Eight repeated score events at 17-24 s versus matching recording events at 8-15 s must be classified `review_required` with an approximately -9 s preferred translation.
2. The same repeated score events already aligned to the recording must classify `pass`.
3. A single coincidental onset must remain `insufficient_evidence`, not become a timing failure or correction proposal.

## Product Reality retest

After merge, use a fresh project for each score candidate so derivatives from a prior score cannot contaminate the comparison.

For the newly checked GP3:

- verify Bass timing first;
- verify Lead and Rhythm against the same recording;
- confirm Source Timing Qualification does not flag a well-aligned source;
- compare the result against the prior GP source before concluding that #397 is an engine defect.
