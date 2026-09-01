# Printed Notation Explicit Rest Events

The printed-notation practice pipeline now preserves **rests as first-class source evidence** rather than treating silence as an unexplained gap.

## Why this is required

The first photographed-score acceptance target explicitly requires rests to create real empty chart regions and prevent false sustains. A missing recognition result and an intentional printed rest are not equivalent.

## Implementation

- `PrintedNotationRestEvent` records measure, beat, duration, confidence, review state, and source image region.
- `SourceRestEvent` preserves that evidence after conversion into the tool-independent imported-source model.
- `SourceTrack.rests` is additive and defaults empty, so existing MIDI/Guitar Pro/MusicXML/PSARC adapters remain compatible.
- Measure completeness now uses interval-union coverage across notes and rests instead of simply summing note durations; overlapping chord notes therefore do not falsely over-count a measure.
- Note/rest overlap is surfaced as a recognition warning.
- `check_printed_notation_explicit_rest_boundaries()` provides a deterministic advisory gate before promotion.

## Initial semantics

For the current monophonic bass practice target, an explicit rest means arrangement-wide silence in that source track. If later polyphonic guitar recognition needs voice-specific rests, voice identity can be added without weakening the current bass invariant.

## BWV1007 relevance

This removes an important blocker before automatic recognition of the first 4–8 Prelude measures. The recognizer can now say either "I found a note" or "the score explicitly says silence" and preserve both claims with confidence and page-region provenance.
