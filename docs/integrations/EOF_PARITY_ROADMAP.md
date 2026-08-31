# Editor on Fire parity roadmap

Last reviewed: 2026-08-30

## Direction

Editor on Fire (EOF) is the project's mature behavioral reference for Guitar Pro intake and Rocksmith authoring semantics. The goal is not to embed EOF or surrender project authority. The goal is to make the generator increasingly EOF-like where EOF has already demonstrated reliable behavior, while preserving this project's provenance, human-review, and fail-closed boundaries.

Each parity slice must be independently testable. EOF-derived evidence is advisory and source/recording-bound; it may reveal a generator defect but never silently rewrites canonical chart state.

## Implemented parity layers

1. **Guitar Pro source compatibility**
   - tuning;
   - MIDI identity;
   - string/fret coordinates;
   - source-relative note timing;
   - supported techniques.

2. **Fret-hand-position evidence**
   - source-bound EOF position markers can be retained and validated as advisory evidence.

3. **EOF-compatible score pre-roll behavior**
   - leading symbolic beats may legitimately precede audio zero after a timing correction;
   - pre-zero anchors are clipped without rejecting the synchronization.

4. **Recording-clock parity**
   - sparse EOF observations from the same score and recording are compared against the final promoted shared timeline;
   - first-playable delta, per-event delta, estimated local bar displacement, median/max error, and constant-offset-vs-drift classification are reported;
   - score hash, recording hash, source track, and shared-timeline hash must remain current.

5. **Alternate Guitar Pro triangulation**
   - a private second GP3/GP4/GP5 full score can be compared locally against the registered score without replacing project authority;
   - Bass, Lead, and Rhythm are independently selected with the normal importer;
   - per-role tuning, note count, first-playable source time, tempo/time-signature structure, and a deterministic prefix of MIDI/string/fret coordinates and onset times are compared;
   - both score hashes are retained and stale/moved evidence fails closed;
   - the Windows EOF reference panel exposes **Compare alternate GP…** so lawful private score variants can be used as diagnostic evidence without entering Git.

This creates a deliberate evidence chain:

**registered GP ↔ alternate GP ↔ EOF source interpretation ↔ EOF recording-clock observations ↔ final Rocksmith arrangement**

Agreement between the two GP sources and EOF source interpretation strongly localizes a remaining mismatch to downstream timing/authoring logic. Disagreement between score sources is surfaced instead of being silently averaged or hidden.

6. **Repeat and alternate-ending unfolding**
   - `src/rocksmith_cdlc_generator/eof_repeat_unfolding.py` unfolds an already-parsed Guitar Pro score's repeat starts/ends and bitmask alternate endings into an EOF-derived realized playback-measure sequence, ported from `eof_unwrap_gp_track()` in EOF's `src/gp_import.c`;
   - it compares that realized sequence against the generator's current written-score-order sequence (the importer does not yet unfold repeats itself) and reports the ordered playback-measure sequence, first/last source-event identity per realized measure, missing/duplicated written measures, and the first position where the two sequences diverge;
   - Da Capo/Da Segno/Coda/Fine-style navigation symbols are explicitly out of scope: PyGuitarPro's parsed object model does not expose the normalized navigation-symbol table EOF's own C code relies on for that slice;
   - the check is advisory-only evidence and never rewrites canonical chart state.

7. **Explicit rest boundary integrity** (first slice of item B, below)
   - `src/rocksmith_cdlc_generator/eof_rest_boundary_check.py` cross-checks every explicit
     rest beat (PyGuitarPro `BeatStatus.rest`, the same empty/rest distinction
     `eof_load_gp()` reads from the beat bitmask in `src/gp_import.c` at
     `c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100`) against the note intervals the generator's
     importer would extract for the same track, and reports any note sustain that overlaps
     an explicit rest's realtime interval;
   - EOF does not branch on the empty/rest distinction itself -- it structurally never
     creates a note event for a beat with no notes, explicit rest or otherwise -- so this
     check reproduces that invariant for our own importer rather than porting an EOF
     algorithm; there is no algorithm to port for this narrow slice;
   - it deliberately does not yet evaluate EOF's separate short-note/staccato/mute
     sustain-truncation preferences (the `note_is_short`/`truncate` logic later in
     `eof_load_gp`), or any sustain extension a later arrangement-generation stage might
     apply; those remain unaudited and are the next slice of item B;
   - the check is advisory-only evidence and never rewrites canonical chart state.

8. **Short-note/staccato/mute sustain-truncation preferences** (second slice of item B, below)
   - `src/rocksmith_cdlc_generator/eof_short_note_truncation_check.py` reproduces EOF's default
     import-preference truncation decision from `eof_load_gp()`: a note shorter than a quarter
     note, or played staccato regardless of duration, is truncated to ~1ms when the relevant
     single-note/chord preference is enabled and the note has no tremolo-picking, bend, vibrato,
     or slide technique; a single (non-chord) fully string-muted or palm-muted note is truncated
     unconditionally on duration under the same technique exemption;
   - it compares that decision against the generator's own currently-imported note sustains and
     reports any note EOF would truncate that the generator still keeps at its full notated
     length -- today, essentially every EOF-truncatable note, since the generator does not yet
     apply this preference on import;
   - it does not yet evaluate generated/exported arrangement output, only directly-imported
     note data; a previously suspected second gap -- a short note being exempted only because
     the *previous* note's legato/shift slide targets it (EOF's cross-beat
     `EOF_NOTE_TFLAG_SLIDE_IN`) -- was investigated against the pinned upstream commit and does
     not exist: `eof_load_gp`'s truncation-eligibility decision runs per note, strictly before
     the only two passes that walk the cross-beat note sequence, so a neighboring note's slide
     cannot influence it (see the check module's top-of-file citation for exact line numbers);
   - the check is advisory-only evidence and never rewrites canonical chart state.

9. **Generated/exported arrangement output boundary integrity** (third slice of item B, below)
   - `src/rocksmith_cdlc_generator/eof_export_boundary_check.py` re-applies the same two
     already-audited EOF decisions (`extract_explicit_rest_intervals` from item 7 and
     `eof_truncation_decision` from item 8, imported and reused rather than re-derived) against
     `reviewed_export_events.reviewed_export_arrangement`'s post-reconciliation/post-
     materialization notes -- the same read model every Bass/Lead/Rhythm authoring path
     consumes on the way to the Rocksmith XML boundary -- instead of the notes the importer
     would directly extract;
   - explicit rests are projected through the promoted reviewed timing map
     (`reviewed_timing_transform.map_reviewed_source_time`) and checked against every
     materialized note's already-reviewed-time interval, so it can catch a reconciliation or
     timing-projection step that stretches a sustain across a rest that was respected at import
     time;
   - EOF's truncation decision is computed per registered-score note and matched to its
     materialized counterpart by source-relative onset time and pitch (MIDI), not string/fret
     (Bass reconciliation may re-voice a note's physical position via `fret_mapping.py`), then
     the predicted post-truncation duration is itself projected through reviewed timing and
     compared against the note's actual materialized sustain;
   - a composed multi-track Lead/Rhythm arrangement (`score_role_composition.py`) is supported:
     every distinct literal contributing registered-score track is resolved
     (`_resolve_source_track_indices`), and each track's own explicit rests and truncation-
     eligible notes are checked only against the materialized notes that resolve back to that
     same literal track, never against another contributing track's unrelated passage, before
     results are pooled into one report; a materialized note whose `source_track_index` is not
     one of the arrangement's declared contributing tracks fails closed rather than being
     silently ignored;
   - a truncatable registered-score note that cannot be matched to exactly one materialized
     note on its own contributing track (expected for some Bass notes that reconciliation
     replaced or dropped in favor of audio evidence) is reported rather than silently skipped;
   - the check is advisory-only evidence and never rewrites canonical chart, timing, or export
     authority.

10. **Note endpoint resnapping/rounding**
    - `src/rocksmith_cdlc_generator/eof_note_endpoint_resnap_check.py` ports the narrow condition
      `gp_import.c`'s note-tail resnap pass corrects for (verbatim comment at that call site:
      "Resnap the end positions of notes that end 1ms after a grid snap position due to floating
      point math rounding error"): a note whose end sits within ~1ms of a beat-grid position
      without landing exactly on it is flagged as a likely tick/time-unit rounding artifact, not
      a real musical gap or overlap;
    - EOF's own grid-snap helper (`eof_is_any_beat_interval_position`) was called from
      `gp_import.c`, `song.c`, and `src/menu/beat.c` during this audit but its own definition was
      not located in the accessible source tree, so this check does not assume any beat-grid
      resolution finer than this project's own imported beat grid
      (`ImportedSource.beat_times_seconds`) -- the calling context in `gp_import.c` is
      specifically about notes already positioned against that same grid, so a ~1ms drift is
      attributable to rounding against it regardless of what finer subdivision the upstream
      helper may also support for unrelated (non-import) EOF editing operations;
    - unlike EOF's own pass, this check is advisory-only (report, not auto-correct) and does not
      resnap tech/bend-point notes glued to a corrected endpoint (this project has no equivalent
      secondary tech-note store), consistent with this project's provenance/review-first
      philosophy for every other EOF-derived check above;
    - applies to any adapter's `ImportedSource`, not only Guitar Pro, since the underlying
      floating-point rounding risk exists in any tick/frame-to-seconds conversion.

11. **Bend strength unit adaptation (import-side data preservation)**
    - `rs.c`'s Rocksmith XML export computes a bend point's `step` attribute (semitones) as the
      note's quarter-step count divided by 2.0; EOF's own bend-strength byte can separately encode
      either half-steps or quarter-steps (a high-bit flag, `bendstrength & 0x80`) -- a detail
      specific to EOF's own C bend-note storage format;
    - this project's PyGuitarPro dependency already normalizes raw GP bytes to real-world units
      before import (`gp3.py:readBend`): `BendPoint.position` is scaled to a 0..12 axis and
      `.value` to whole semitones (`bendSemitone=25`), so there is no quarter-step/half-step byte
      encoding left to decode on this project's side -- PyGuitarPro has already done that,
      confirmed by reading its own decoding source rather than assumed;
    - `guitarpro_import.py:_bend_points()` reads each note's already-normalized bend curve and
      re-scales only the 0..12 position axis to this project's own 0.0-1.0 fraction-of-note-
      duration convention, storing it in a new additive `SourceNoteEvent.bend_points` field
      (previously this data was discarded entirely at import, down to a boolean `"bend"`
      technique flag);
    - import-side preservation only: Rocksmith XML export of the captured curve is not
      implemented in this slice -- `bend` remains excluded from `rocksmith_xml.py`'s
      `DIRECT_NOTE_TECHNIQUES`, so a bent note still fails closed at the reviewed-XML boundary
      rather than being silently exported without its bend. Propagating the curve through
      `reviewed_export_events.py` and emitting `<bendValues>` elements is the next slice.

12. **Slide subtype unit adaptation (import-side data preservation)**
    - this project previously collapsed all six of PyGuitarPro's `SlideType` subtypes
      (`intoFromAbove`/`intoFromBelow`/`shiftSlideTo`/`legatoSlideTo`/`outDownwards`/
      `outUpwards`, audited directly from PyGuitarPro's own parsed object model) into one
      generic `"slide"` technique flag -- `eof_rocksmith_validation.py` already documents the
      resulting gap explicitly via its `rocksmith_slide_detail_missing` warning;
    - **EOF audit finding, added after review**: `raynebc/editor-on-fire` `src/gp_import.c`
      (audited at commit `c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100`) reads the Guitar Pro
      slide-type byte during
      import (`if(byte2 & 8) { ...; byte = pack_getc(inf); ... }`, appearing twice --
      once in the standalone `parse_gp()` debug utility and once in `eof_load_gp()`) but never
      branches on the value: it is logged for diagnostics only and is not mapped to any EOF
      note flag. EOF's own GP importer therefore has **no existing behavior to port** for the
      GP-slide-subtype-to-flag mapping step itself. EOF's Rocksmith-facing slide model --
      `EOF_PRO_GUITAR_NOTE_FLAG_SLIDE_UP`/`_SLIDE_DOWN` (derived by comparing a note's explicit
      target fret against its own fret) and `_UNPITCH_SLIDE` (no target fret) -- is instead
      populated on **Rocksmith XML re-import** in `src/rs_import.c`'s
      `eof_rs_import_note_tag_data()`, from the `slideTo`/`slideUnpitchTo` XML attributes, not
      from Guitar Pro import at all. This project's `slide_kinds` field is therefore sourced
      directly from PyGuitarPro's own already-parsed `SlideType` enum with no EOF C behavior
      standing behind the import-side mapping (unlike the bend/pinch-harmonic/resnap slices
      above, which do port an active EOF decision); EOF's `rs_import.c` model above is the
      relevant reference for the *export* slice instead, once target-fret resolution exists;
    - `guitarpro_import.py:_slide_kinds()` now captures the specific subtype(s) present on a
      note into a new additive `SourceNoteEvent.slide_kinds` field, leaving the existing
      generic `"slide"` entry in `techniques` completely unchanged -- `eof_rocksmith_validation.
      py`'s `SPECIALIZED_UNSUPPORTED_TECHNIQUES` check and `reviewed_techniques.py`'s
      `SUPPORTED_TECHNIQUES` whitelist both already depend on that exact string, and neither
      recognizes finer-grained labels, so adding one directly to `techniques` would have been
      silently filtered or rejected -- confirmed by reading both modules before choosing the
      separate-field design, not assumed;
    - does not resolve a pitched slide's target fret (GP encodes this implicitly as the next
      same-string note, not as an explicit value PyGuitarPro exposes) or attempt Rocksmith XML
      export (`slideTo`/`unpitchSlideTo` attributes per `rs.c`) -- `"slide"` remains outside
      `rocksmith_xml.py`'s `DIRECT_NOTE_TECHNIQUES`, so a sliding note still fails closed at the
      reviewed-XML boundary exactly as before this change. No oracle/differential test against
      EOF is added for the import-mapping step because EOF has no comparable behavior to
      differentially test against, per the audit finding above; a differential test comparing
      export-side output against `rs_import.c`'s flag semantics is appropriate once export
      lands.

13. **Pinch harmonic export attribute adaptation (active bug fix, not just data preservation)**
    - `gp_import.c` reads GP's raw harmonic-type byte (1=natural, 2=artificial, 3=tapped,
      4=pinch, 5=semi) and sets `EOF_PRO_GUITAR_NOTE_FLAG_HARMONIC` only for type 1; every other
      type sets `EOF_PRO_GUITAR_NOTE_FLAG_P_HARMONIC` under the default-off
      `eof_gp_import_nat_harmonics_only` preference in `main.c`; `rs.c` exports these as two
      separate XML attributes, `harmonic` and `harmonicPinch`;
    - PyGuitarPro's own parsed model already exposes this exact five-way distinction
      (`NaturalHarmonic`/`ArtificialHarmonic`/`TappedHarmonic`/`PinchHarmonic`/`SemiHarmonic`,
      `HarmonicEffect.type` 1-5, confirmed to match GP's byte convention by reading PyGuitarPro's
      own class definitions), but this project previously collapsed all five into one generic
      `"harmonic"` label that `rocksmith_xml.py` exported uniformly as `harmonic="1"` -- an
      **active correctness bug**, not a missing-detail gap: a pinch harmonic was exported
      indistinguishable from a natural one, and the existing `pinchHarmonics` arrangement
      property (already declared in `_ARRANGEMENT_PROPERTY_NAMES`) was never populated;
    - `_techniques()` now tags only natural harmonics `"harmonic"`; every other GP harmonic type
      is tagged `"harmonic_pinch"` (added to both `reviewed_techniques.SUPPORTED_TECHNIQUES` and
      `rocksmith_xml.DIRECT_NOTE_TECHNIQUES` so it's reviewed/exported like any other supported
      technique); `rocksmith_xml.py` emits `harmonicPinch="1"` (not `harmonic="1"`) for it and
      sets the `pinchHarmonics` arrangement property.

## Next high-value parity checks

### B. Rest, tie, and sustain boundaries (remaining slices)

Explicit rest boundary integrity (item 7) and short-note/staccato/mute sustain-truncation
preferences (item 8) against directly-imported note intervals are now checked. Item 8's
previously suspected cross-beat legato/shift slide-in truncation exemption was investigated
against the pinned upstream commit and does not exist in EOF's import-time truncation decision
(see item 8 above). Item 9 extends both of those checks to generated/exported arrangement
output (post-reconciliation/post-materialization notes), including a composed multi-track
Lead/Rhythm arrangement (each contributing track's rests/truncation facts are matched only
against materialized notes resolved back to that same literal track). The remaining scope:
section boundaries (the generator does not yet carry an EOF-comparable section/phrase model to
check against; see roadmap item F).
Tied notes are covered separately by the existing tie-continuation slice (item "Exact
tie-continuation behavior" in `THIRD_PARTY_NOTICES.md`).

Acceptance target: EOF and generator agree on onset, duration/end, tie continuation, and
explicit-rest gaps for sampled events, including generated/exported arrangement output (single-
track and composed multi-track), not only directly-imported note data. Section-boundary parity
remains open.

### C. Beat/measure numbering parity

Expose the same realized measure position that EOF uses after repeats are unfolded. This is required for useful official-TAB synchronization and for diagnosing errors such as "audio is at bar 34 while generated material is at bar 36."

Acceptance target: sparse EOF bar/beat observations resolve to the same realized bar and beat in Song Workspace.

### D. Chord and fingering semantics

Compare simultaneous-note grouping, chord shapes, fingering/hand-position decisions, and string choices. Preserve authored string/fret choices whenever valid instead of re-voicing equivalent pitches unnecessarily.

### E. Technique semantics

Deepen parity for bends, slides, hammer-ons, pull-offs, palm muting, harmonics, vibrato, tremolo, tapping, and other Rocksmith-relevant techniques only where EOF behavior is reproducible and the project supports the technique.

### F. Section, phrase, and anchor behavior

Compare EOF's useful section/phrase boundaries and anchor placement with the generated Rocksmith authoring model. The objective is stable playable navigation and hand positioning, not blind replication of editor internals.

### G. Final Rocksmith export parity

For a lawful local fixture, compare the final generator-authored XML/arrangement semantics with an EOF-produced reference: note timing, chord grouping, sustains, techniques, anchors, sections, phrases, and arrangement metadata.

## Product Reality rule

When a packaged real-song test disagrees with EOF, the real observation wins over a synthetic green test. Reopen the defect, capture the smallest lawful source-bound EOF evidence needed to reproduce it, add that evidence shape to the checker, and only then encode a general fix. Never add artist/title checks, fixed song offsets, or one-off bar corrections.
