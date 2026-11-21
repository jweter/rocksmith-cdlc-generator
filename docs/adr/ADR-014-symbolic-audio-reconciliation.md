# ADR-014: Symbolic/audio Bass reconciliation

## Status
Accepted

## Context
Imported MIDI, Guitar Pro, and MusicXML sources can now be aligned to the analyzed recording beat grid. Alignment alone does not establish that the symbolic notes are musically correct. The project also has an audio-derived Bass transcription with pitch, onset, and confidence evidence.

## Decision
Add a reconciliation layer that compares aligned symbolic notes against audio-derived Bass notes using conservative onset pairing and exact MIDI-pitch agreement.

Evidence is classified as:

- `verified_match`: symbolic and audio evidence agree on pitch inside the onset window.
- `pitch_conflict`: an audio onset is nearby but MIDI pitch differs.
- `symbolic_only`: no audio-derived note is found near the aligned symbolic onset.
- `audio_only`: an audio-derived note remains unmatched by the symbolic source.

A `verified_match` is promoted to `symbolic_verified` only when the onset delta is within the stricter verification threshold, audio confidence is high enough, alignment-region confidence is high enough, and the audio transcription does not already require review.

Reconciliation writes a candidate chart to `charts/bass_reconciled.json` and disagreements to `review/source_disagreements.json`. It does not mutate the original imported source or silently discard conflicting evidence.

## Consequences
Structured notation can now reduce manual work when independent audio evidence supports it, while disagreements remain explicit review items. Guitar Pro string/fret and technique information is preserved on symbolic candidates. Audio-only detections remain visible rather than being erased by the tab.

## 2026-11 evidence-promotion hardening (algorithm v3; #787)

**Critical distinction:** an audio-derived note aligned to a score note is an *observation*, not sufficient proof of musical truth. The old `verified_match` status can still describe an observed pitch/onset coincidence, but `symbolic_verified` trust and `review_required=false` now require all of the following independently:

1. **Verified Bass stem provenance.** The transcription source must resolve to the project's `stems/bass.wav`, whose hash-bound local receipt matches the current `audio/normalized.wav` hash and stem bytes. Full mixes, filtered mixes, missing receipts, off-project paths and stale stem files **never promote** notes.
2. **Independent confidence components.** Overall audio confidence >=0.70, pitch confidence >=0.60, timing confidence >=0.75, alignment region confidence >=0.70, strong onset match <=0.08 seconds and audio `review_required=false`.
3. **No silent score rewrite.** Musical disagreements remain review-required, and the score imported source remains immutable. The `verified_match` status without verified source remains `symbolic_unverified`; it is not a musical PASS.

Algorithm v3 records `audio_evidence_provenance` on the reconciled chart. V2 artifacts are stale and must be regenerated, so prior permissive verification cannot survive an update. The thresholds are intentionally conservative defaults, **not calibrated proof that an arbitrary separator produces true notes**; independent synthetic and legal ground-truth benchmarks are still required.

The recording provenance checks guard source/derived-file identity, not separator content quality, model accuracy, or processing delay. Audio stem content-time alignment and quantitative isolation quality need their own separate Product Reality gates.
