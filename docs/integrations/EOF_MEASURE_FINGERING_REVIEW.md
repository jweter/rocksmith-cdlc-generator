# EOF-inspired measure and fingering review

Last reviewed: 2026-08-22

## Purpose

Bring the most useful Editor on Fire (EOF) authoring interaction pattern into Song Workspace without importing EOF edits or making EOF canonical project authority: review the song one musical bar at a time while seeing the physical string/fret placements for that bar immediately.

This slice is an original project-owned implementation informed by observed EOF workflow behavior. It does not copy or vendor EOF source or binaries.

## Product behavior

Arrangement Preview now includes a **Measure fingering inspector · EOF-inspired** panel above the full-song arrangement canvas.

For the currently selected Bass, Lead, or Rhythm arrangement it shows:

- current bar number and total bar count;
- time signature;
- authoritative recording-time start/end for the bar;
- every note onset in the bar with local bar offset, note/MIDI identity, physical string, fret, techniques, and review-required state;
- observed fretted range for the bar;
- active physical strings;
- open-string count;
- unresolved-position count;
- review-required count;
- current EOF hand-position evidence count when source-bound advisory evidence exists for the selected arrangement.

**Previous bar** and **Next bar** seek directly to bar boundaries. **Follow play/seek cursor** keeps the inspector synchronized with normal preview navigation. Selecting a row seeks to that exact event.

## Timing authority

The inspector does not invent fixed-duration bars.

For current GP3/GP4/GP5 score fan-out, the project Guitar Pro adapter preserves each Guitar Pro measure header as a `SourceTimeSignatureEvent`; those source-bound measure starts are projected through the reviewed shared timeline and used as exact bar boundaries in Arrangement Preview.

For a source exposing only one time-signature event, the inspector may derive later measure starts only when an existing canonical beat grid is present and the signature resolves to an integral number of quarter-note beats. If neither form of timing authority exists, the measure inspector reports itself unavailable rather than guessing.

## Fingering semantics

The displayed fret range is deliberately **descriptive**, not an optimized or accepted fret-hand position.

Examples:

- `observed frets 5-9` means notes in the current bar already carry pitch-correct project positions between frets 5 and 9;
- open strings are counted separately and are not used to inflate the fretted range;
- unresolved string/fret positions remain explicit;
- review-required events remain explicit.

This slice does not choose alternate strings, minimize hand movement, generate Rocksmith anchors, or accept playability.

## EOF evidence boundary

Existing source-bound EOF fret-hand-position evidence remains advisory. When a current evidence status exists for the active arrangement, the bar inspector displays the number of observed EOF markers as context only.

Viewing a bar or an EOF evidence count does **not**:

- accept a string/fret position;
- change the registered score;
- change Bass/Lead/Rhythm mapping;
- change shared timing;
- change techniques;
- create Rocksmith fret-hand-position anchors;
- satisfy validation or packaging gates.

## Why this is the next useful EOF-derived slice

EOF is especially effective because it keeps the author oriented in musical structure rather than forcing inspection of thousands of flat events. This panel applies that same product principle to the generator's own provenance-aware data model: local musical context first, exact event detail immediately beneath it, and explicit review state preserved.

The next EOF-focused investigation should continue the existing `EOF_FRET_HAND_POSITION_INVESTIGATION.md` evidence contract. A true global hand-position optimizer remains blocked until independently reviewed EOF observations justify specific hard/soft transition rules and weights.

## Tests

`tests/test_eof_measure_review.py` covers:

- Guitar Pro measure-header boundary interpretation;
- deterministic measure lookup at boundaries;
- observed fret-span/open-string/unresolved-position summaries;
- onset ownership of events by bar.
