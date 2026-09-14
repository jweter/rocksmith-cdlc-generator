# EOF timing-edit anchor audit

Issue: #414

## Scope

This audit closes one bounded investigation slice from the EOF subsystem parity matrix: **Timing edits preserving anchors**. It is evidence-only and does not modify Rocksmith timing authority, chart state, private media, or Product Reality.

## Pinned EOF evidence

This audit is pinned to `raynebc/editor-on-fire` commit `4a724f4b068b4dd11a71a4b688707a0ed35b6563`, the same upstream revision already used by the repository's EOF parity roadmap.

Smallest relevant source surfaces at that revision:

- `src/beat.h`: `eof_recalculate_beats()` is documented to recalculate the anchors before and after the edited beat from their floating-point timestamps and update the beats between them; the same header documents beat-position calculation from the previous beat tempo and the first-beat/MIDI-delay special case.
- `src/beat.c`: `eof_recalculate_beats()` resolves `eof_find_previous_anchor()` and `eof_find_next_anchor()` around the edited beat before recomputing the bounded region. The same source contains the tempo-map-lock guard used by beat-map validation/editing paths.
- `src/song.h`: the audio profile's signed `midi_offset` is the persisted leading-offset authority used by first-beat/leading-silence workflows.
- EOF's bundled help/tutorial at the same revision documents the Leading Silence workflow and first-beat synchronization behavior; it is supporting user-facing documentation, not a substitute for the source-level anchor evidence above.

These pinned paths/functions are the reproducibility boundary for this audit. If upstream EOF changes later, the parity fixture must continue to cite this SHA unless a deliberate re-audit updates the reference.

## Reference behavior

Editor on Fire's beat-editing model treats anchor beats as local synchronization boundaries rather than free-floating decoration:

- Moving/anchoring a beat establishes a fixed synchronization point.
- Adjusting a beat later in the song changes the beats between that point and the previous/next synchronization anchors instead of freely shifting all prior synchronized timing.
- Recalculation around an edited beat is bounded by the previous and next anchors where both exist; if no later anchor exists, recalculation may extend to the project end.
- A locked tempo map is an explicit guard against ordinary tempo-map correction/editing.
- Beat zero is tied to the current audio profile's MIDI-delay/leading-offset authority rather than being treated as an arbitrary arrangement-local translation.

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

The fixture should be differential where practical: compare the expected local-anchor semantics against the pinned EOF revision above, while retaining this project's stricter fail-closed review/provenance gates.

## Non-goals

- No song-specific offset.
- No commercial/private GP or audio fixture.
- No live EOF runtime dependency.
- No relaxation of human timing review.
- No claim that packaged Rocksmith timing Product Reality is verified.

## Result

The EOF behavior is now source-bound to an exact upstream revision and sufficiently bounded to implement a deterministic parity fixture without guessing at GUI mechanics. The next engineering step for this matrix row is the synthetic anchor-preservation regression described above; only after that comparison is GREEN should the row move beyond PARTIAL.

## Deterministic fixture implemented (2026-09-14)

`tests/test_score_timing_anchor_bounded_edit.py` implements the fixture described above against the existing `score_timing_anchors._bounded_refit_regions()` bounded-refit engine:

- Four human anchors at source beats 0, 3, 6, 9 (three bounded regions), with notes before (beat 1), inside (beat 3 itself), and after (beat 8) the edited region.
- One edit moves the interior anchor at beat 3 from recording time 3.0s to 3.6s.
- `test_editing_interior_anchor_only_recomputes_its_bounded_regions` asserts the far region `[6, 9]` (and the note at beat 8 inside it) is exactly unchanged; only the two regions bounded by beat 3 are re-derived; and the anchors bounding the whole edit from the outside (beat 0, beat 6) keep their own recording times exactly -- the same bounded-recalculation invariant as EOF's `eof_recalculate_beats()`.
- `test_editing_interior_anchor_invalidates_previously_accepted_refit` asserts a `ScoreTimingRefitAcceptance` recorded against the pre-edit preview fails `require_current_acceptance()` against the post-edit preview (the provenance/rebuild-not-mutate non-goal), and that the shared `SharedTimeline.inherited_roles` identity (Bass, Lead, Rhythm) is what carries this invalidation to every arrangement at once rather than per-role state.

This closes the deterministic-fixture gap for this matrix row's bounded-recalculation invariant. The row remains PARTIAL: EOF's locked-tempo-map editing guard and first-beat/MIDI-delay leading-offset semantics (`src/song.h`'s `midi_offset`) are architecturally distinct from this project's shared-recording-clock model and are not yet covered by a fixture here; the "Chart delay / non-zero first beat" matrix row tracks that leading-offset semantics separately.
