# Live review Product Reality pass (#379-#382)

Last reviewed: 2026-08-22

This pass turns the EOF/Rocksmith-inspired Arrangement Preview from a read-only visualizer into a practical human review surface while preserving the generator's existing authority boundaries.

## Playback and latency

Arrangement Preview reuses the existing `ProjectAudioTransport`; it does not create a second clock. Local Play/Pause, Stop, +/-5s, First note, and Next note controls operate the same transport used by Timeline. Arrangement changes preserve song position.

The live preview now suppresses expensive hidden Timeline redraws while another notebook tab is visible. A small diagnostic reports live render duration and the transport-to-painted-clock delta so Product Reality tests can distinguish chart timing errors from Tk rendering latency. No musical timing offset is applied to compensate for UI delay.

## Physical playability

Guitar validation now checks simultaneous fretted chord span while excluding open/muted strings. A span of seven or more frets is a blocking `implausible_chord_fret_span` finding; five or six frets is a warning requiring explicit review. These thresholds are deliberately conservative and validation never rewrites fingering.

## Human review marks

Clicking a rendered 2D note or perspective note selects the underlying preview event. The selection shows arrangement, event index, onset, MIDI pitch, string, fret, techniques, trust class, and confidence.

The reviewer can mark the selected event `questionable`, `wrong`, or clear the mark. Marks are stored in `review/human_note_marks.json` and bound to the current score/source SHA so they fail closed as stale evidence if the underlying score changes.

For Lead/Rhythm, changing a mark immediately refreshes guitar validation:

- `questionable` becomes a high-priority human-review warning;
- `wrong` becomes a blocking validation failure;
- clearing the mark removes that human finding on revalidation.

The mark changes review authority only. It does not mutate pitch, string/fret placement, timing, techniques, score mapping, or source provenance.

## Visual semantics

Selected notes receive an accent outline. Human `questionable` marks receive a warning outline and `?`; human `wrong` marks receive a danger outline and `X`. These remain independent of the source's own review-required state.
