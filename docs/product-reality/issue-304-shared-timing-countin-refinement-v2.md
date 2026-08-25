# Product Reality — shared timing count-in refinement v2

Parent: #304  
Related: #397, PR #398, PR #412

## Fresh packaged evidence

On Windows build `v0.1.0 · 27caa264`, the representative **For Whom the Bell Tolls** project still renders Bass, Lead, and Rhythm first events at roughly 17.7–17.9 s while the actual arrangements enter around 8–9 s. The recording transport and click/beat grid remain aligned. The same late translation therefore affects all three score-derived arrangements.

PR #412 correctly routed Arrangement Preview through promoted `reviewed_score_timing.json`, which proves the remaining defect is upstream of preview rendering: the promoted timing authority is carrying the wrong global score-to-recording translation.

## Root cause in the first onset-refinement design

PR #398 added content-aware Bass onset refinement, but its correction path had two Product Reality gaps:

1. **Score-only pre-roll could not be represented during correction.** `_shift_report()` rejected any global correction that moved an existing alignment anchor before recording time zero. A structured score with count-in/intro measures legitimately needs early symbolic beats to map before the recording begins. The real correction can therefore be negative even though the first persisted in-recording anchor must remain non-negative.
2. **Timing evidence was coupled too tightly to trusted pitch.** The original refinement discarded every transcription event marked `review_required` and required very high pitch confidence. That is unnecessarily strict for a timing-only global translation and can leave a real recording with too little evidence even when onset timing is strong.

The synthetic regression in PR #398 started its first audio anchor at +10 s, so a -10 s correction landed exactly at zero and did not exercise the score-count-in case where an earlier anchor would cross zero.

## Fix

The next alignment semantics are versioned as `beat-grid-piecewise-linear-v3`, intentionally making persisted v2 alignment authority stale so existing projects are offered the safe automatic alignment step again.

Alignment onset refinement v2:

- scores one-to-one onset agreement across the first symbolic events;
- gives additional weight to reliable equal-pitch matches without requiring every timing event to have trusted pitch;
- can use review-required transcription events only when their timing confidence remains strong;
- permits a negative global translation by dropping only transformed anchors that lie before recording time zero;
- retains at least two in-recording anchors and lets the piecewise-linear transform extrapolate score-only pre-roll naturally to negative recording time;
- still refuses ambiguous/weak corrections rather than guessing;
- invalidates promoted shared/reviewed timing and downstream arrangement/validation derivatives whenever alignment is regenerated.

No song-specific offset is encoded.

## Regression contract

A synthetic score with notes at 17–24 s and a recording performance at 8–15 s must recover a -9 s translation even when the score starts at recording beat zero and the correction would move its earliest alignment anchor before zero. The retained alignment anchors must remain non-negative, and source time 17 s must map to recording time 8 s.

## Expected packaged retest

After this change merges, the existing Product Reality project should no longer treat its v2 `analysis/alignment.json` as current. Running safe automatic steps should rebuild alignment/refinement, invalidate old promoted timing derivatives, and return the project to the existing human timing-review/promotion gate. The next packaged verification must confirm Bass/Lead/Rhythm early entrances and the previously observed silent-gap sustain region before #397 can be considered resolved.
