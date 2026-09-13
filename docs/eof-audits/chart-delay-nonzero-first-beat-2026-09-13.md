# EOF audit: chart delay and non-zero first beat

Issue: #414

Reference upstream: `raynebc/editor-on-fire`
Audited commit: `4a724f4b068b4dd11a71a4b688707a0ed35b6563` (2026-09-10)

## Finding

EOF treats a non-zero first beat as explicit project timing state rather than silently assuming beat zero begins at recording time zero.

Concrete upstream evidence:

- `src/drumbeats.c` checks `eof_song->beat[0]->pos != 0` before MIDI/drum-beat export and attempts `eof_replace_chart_delay_with_beat()` so the leading delay is represented structurally when the target format needs a beat at zero.
- `src/rs_import.c` stores imported beat timestamps directly into the EOF beat map and, for the first beat, updates the chart/MIDI delay from that first-beat position.
- EOF's user-facing project behavior allows the first beat marker to be moved independently, confirming that first-beat position is editable timing authority rather than a derived cosmetic label.

## Implication for this project

The generator must continue to preserve a non-zero recording/chart origin as explicit shared timing state. A first beat that does not occur at 0 s must not be normalized away, double-counted as intro silence, or repaired with a song-specific offset.

This reinforces the existing architecture from #413/#455:

1. preserve the source/project beat origin explicitly;
2. keep one shared recording clock for Bass, Lead, and Rhythm;
3. translate symbolic events through that shared authority exactly once;
4. treat export-format requirements for a zero-time beat as a boundary transformation, not a change to canonical musical timing;
5. fail closed when source timing and recording timing are inconsistent rather than silently shifting the chart.

## Parity status

`Chart delay / non-zero first beat` remains **PARTIAL** rather than PARITY. This audit establishes EOF's reference semantics and removes ambiguity about whether a non-zero first beat is valid. The remaining engineering gate is deterministic fixture coverage proving our import/alignment/export boundaries preserve that state without double application.

## Next deterministic fixture

Add a media-safe synthetic case with:

- first authoritative beat at a non-zero timestamp;
- at least one symbolic event after that beat;
- one shared Bass/Lead/Rhythm timing authority;
- assertions that imported/shared event positions retain the intended phase exactly once;
- export-boundary assertions that any required zero-time beat insertion does not mutate canonical event timing.

No commercial audio, score, Ubisoft-derived material, or private source is required for this fixture.
