# EOF timing-edit anchor audit

Issue: #414

## Scope

This audit closes one bounded investigation slice from the EOF subsystem parity matrix: **Timing edits preserving anchors**. It is evidence-only and does not modify Rocksmith timing authority, chart state, private media, or Product Reality.

## Reference behavior

Editor on Fire's documented beat-editing model treats anchor beats as local synchronization boundaries rather than free-floating decoration:

- Moving/anchoring a beat establishes a fixed synchronization point.
- Adjusting a beat later in the song changes the beats between that point and the previous anchor instead of freely shifting all prior synchronized timing.
- Deleting an intermediate beat recalculates the previous anchor's BPM so the remaining beats fit between surrounding anchors.
- Locking the tempo map disables most timing edits after synchronization while still allowing the first beat/MIDI delay to move for leading-silence/resync workflows.
- Resetting the first-beat offset to zero inserts leading beats while preserving the original positions of existing notes, beats, and text events.

These semantics are relevant to this project's reviewed timing workspace because they separate two concepts that must not be conflated: changing a local beat interval versus translating the entire reviewed score-to-recording authority.

## Current generator boundary

Rocksmith CDLC Generator already has a stronger architectural invariant than EOF's manual editor: Bass, Lead, and Rhythm consume one shared reviewed recording clock. A timing edit must therefore preserve shared-authority identity and provenance rather than becoming an arrangement-local offset.

The current parity status remains **PARTIAL**. This audit does not claim behavioral parity because no differential fixture yet proves that local reviewed timing edits preserve adjacent fixed anchors with EOF-equivalent interval recomputation.

## Deterministic next fixture

A repository-safe synthetic fixture should contain:

1. a beat map with at least three explicit synchronization anchors;
2. notes before, inside, and after the middle anchored region;
3. one edit that moves an interior beat inside that region;
4. expected invariants that the previous and next anchors remain fixed, only the bounded interval is re-derived, and all three arrangements continue to consume the same resulting shared clock;
5. provenance assertions showing the edit invalidates/rebuilds downstream timing derivatives rather than mutating arrangement-local timestamps in place.

The fixture should be differential where practical: compare the expected local-anchor semantics against the pinned EOF reference behavior, while retaining this project's stricter fail-closed review/provenance gates.

## Non-goals

- No song-specific offset.
- No commercial/private GP or audio fixture.
- No live EOF runtime dependency.
- No relaxation of human timing review.
- No claim that packaged Rocksmith timing Product Reality is verified.

## Result

The EOF behavior is now sufficiently bounded to implement a deterministic parity fixture without guessing at GUI mechanics. The next engineering step for this matrix row is the synthetic anchor-preservation regression described above; only after that comparison is GREEN should the row move beyond PARTIAL.
