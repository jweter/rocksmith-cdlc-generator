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
   - it does not model the narrow case where a short note is exempted only because the
     *previous* note's legato/shift slide targets it (EOF's cross-beat
     `EOF_NOTE_TFLAG_SLIDE_IN`), and it does not yet evaluate generated/exported arrangement
     output, only directly-imported note data;
   - the check is advisory-only evidence and never rewrites canonical chart state.

## Next high-value parity checks

### B. Rest, tie, and sustain boundaries (remaining slices)

Explicit rest boundary integrity (item 7) and short-note/staccato/mute sustain-truncation
preferences (item 8) against directly-imported note intervals are now checked. The remaining
scope: whether sustains generated later in the pipeline (arrangement generation/export, not just
import) still respect explicit-rest, truncation-preference, and section boundaries, and the
cross-beat legato/shift slide-in truncation exemption named in item 8.
Tied notes are covered separately by the existing tie-continuation slice (item "Exact
tie-continuation behavior" in `THIRD_PARTY_NOTICES.md`).

Acceptance target: EOF and generator agree on onset, duration/end, tie continuation, and
explicit-rest gaps for sampled events, including generated/exported arrangement output, not
only directly-imported note data.

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
