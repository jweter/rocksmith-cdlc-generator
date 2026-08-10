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
