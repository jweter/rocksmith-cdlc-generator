# Third-Party Notices

## Editor on Fire

Rocksmith CDLC Generator uses **Editor on Fire (EOF)** as a reference implementation for mature Guitar Pro and Rocksmith authoring behavior. Portions of this project's timing design are already adapted from EOF behavior, and issue #414 establishes a standing program for additional tested parity/adaptation where useful.

### Primary current upstream

Repository: `raynebc/editor-on-fire`  
Upstream copyright: Copyright (c) 2018, T^3 Software  
Upstream license: BSD-style 3-clause license (`license.txt` in the EOF repository)

The upstream license permits redistribution and use in source and binary forms, with or without modification, provided its copyright notice, conditions and disclaimer are retained and contributor names are not used to endorse or promote derived products without specific prior written permission.

### Historical snapshot used by the first timing parity fix

Repository: `Berneer/editor-on-fire`

PR #413's initial timing investigation inspected the Guitar Pro / Go PlayAlong timing implementation in `src/gp_import.c` and related declarations in `src/gp_import.h` from this historical snapshot. The relevant behavior was the ability to synchronize symbolic beats before audio time zero, omit the pre-zero portion and continue mapping later score content through the project beat map instead of rejecting the valid transform.

New EOF audits should normally begin with the current `raynebc/editor-on-fire` lineage so later fixes are not missed. Historical forks remain useful for provenance and comparison.

### EOF first-synchronization-point timing adaptation

Issue #455 re-audited the current primary upstream at commit
`c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100`, especially
`src/gp_import.c`.

The v6 Guitar Pro timing path in
`src/rocksmith_cdlc_generator/eof_first_sync_alignment.py` is a clean Python
adaptation of the timing semantics relevant to the Product Reality failure:

- realtime note positions are derived from the project beat map and fractional beat position;
- a synchronization point may occur after the beginning of the score;
- beats preceding that synchronization point are walked backward using the beat duration in effect;
- beats that would remain before recording time zero are omitted rather than causing a valid synchronization to be rejected;
- later score content remains on the retained project beat map without a second independent intro offset.

The Python implementation does not copy EOF's C source verbatim and does not bundle or launch EOF. It records the exact upstream repository, file and commit in its generated evidence artifact. The project's separate audio evidence is used only to identify which recording occurrence corresponds to the complete score's first playable synchronization point; once selected, the beat-map translation follows the EOF-derived pre-zero semantics above.

### Repeat and alternate-ending unfolding adaptation

Issue #414's parity item A re-audited the current primary upstream at commit
`c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100`, specifically `src/gp_import.c`'s
`eof_unwrap_gp_track()` function.

`src/rocksmith_cdlc_generator/eof_repeat_unfolding.py` is a clean Python adaptation of that
function's repeat-start, end-of-repeat, and alternate-ending decision logic:

- a measure marked as a start of repeat resets the current repeat-pass counter the first time
  it is reached;
- a measure with alternate-ending markers is only realized on the repeat pass(es) its bitmask
  selects, and is otherwise skipped forward to the next measure that closes the alternate
  ending's scope, without being realized;
- reaching an end-of-repeat measure with passes remaining jumps back to the most recent start
  of repeat and advances the pass counter; the repeat count is only decremented when the
  measure being left is not itself the currently active alternate ending.

The Python implementation does not copy EOF's C source verbatim and does not bundle or launch
EOF. It intentionally does not port that same function's separate navigation-symbol branches
(Da Capo / Da Segno / Coda / Fine): EOF resolves those from a `gp->symbols` table it populates
while parsing the raw Guitar Pro binary, and PyGuitarPro's parsed object model (this project's
Guitar Pro import dependency) does not expose an equivalent normalized table, so that slice is
explicitly out of scope rather than approximated. The module also verified, by reading
PyGuitarPro's own GP3/GP5 readers (`repeatClose`/`repeatAlternative` handling in `gp3.py` and
`gp5.py`), that PyGuitarPro already normalizes the on-disk repeat-count off-by-one (GP5) and
alternate-ending bitmask (GP3/GP4/GP5) the same way EOF's own version-dependent branches do, so
no separate per-version branch was needed in the port.

This check is advisory only: it reports whether the generator's currently-unimplemented
repeat/alternate-ending unfolding (written score order) agrees with EOF-derived realized
playback order, and never rewrites canonical chart state.

### Explicit rest boundary integrity adaptation

Issue #414's parity item B re-audited the current primary upstream at commit
`c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100`, specifically the per-beat rest-type
handling inside `eof_load_gp()` in `src/gp_import.c`: a beat bitmask bit signals
whether the beat is a rest, and a following byte distinguishes an "empty" beat
(no notes authored, no rest symbol written) from a "rest" beat (the score
explicitly notates silence) -- but EOF reads and discards that byte without
branching on it. Either way, EOF's parser never creates a note event for a
beat with no notes, so the actual invariant enforced is structural rather than
a ported algorithm.

`src/rocksmith_cdlc_generator/eof_rest_boundary_check.py` reproduces that same
structural invariant for this project's own Guitar Pro importer: it reads
PyGuitarPro's own `BeatStatus.rest` normalization of the same empty/rest
distinction, computes every explicit rest beat's realtime interval, and
cross-checks it against the note intervals the generator's importer would
extract for the same track, reporting any note sustain that overlaps an
explicit rest.

The Python implementation does not copy EOF's C source and does not bundle or
launch EOF. It does not evaluate EOF's separate short-note/staccato/mute
sustain-truncation preferences later in the same function, which remain
unaudited and out of scope for this slice.

This check is advisory only: it reports whether the generator's directly
imported note intervals respect explicit-rest boundaries, and never rewrites
canonical chart state.

### Short-note/staccato/mute sustain-truncation adaptation

Issue #414's parity item B re-audited the current primary upstream at commit
`c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100`, specifically the `note_is_short`
determination, the staccato/mute/palm-mute truncation-eligibility branches, and
the corresponding `eof_gp_import_truncate_short_notes` /
`eof_gp_import_truncate_short_chords` / `eof_gp_import_remove_accent_from_staccato`
preference declarations and defaults (`1`, `0`, `0` respectively) in `src/main.c`,
inside and after `eof_load_gp()` in `src/gp_import.c`.

`src/rocksmith_cdlc_generator/eof_short_note_truncation_check.py` is a clean Python
adaptation of that decision logic:

- a note shorter than a quarter note (after tuplet/dotted scaling, which
  PyGuitarPro's own `Duration.time` already reports in absolute ticks) is
  "short"; a note played staccato is unconditionally "short" regardless of its
  notated duration;
- a short note is only actually truncated when the relevant import preference
  (single notes vs. chords, by note count) is enabled, the note lacks tremolo-
  picking status, and the note has no bend, vibrato, or slide technique
  (EOF's `EOF_NOTE_TFLAG_DONT_TRUNCATE` override);
- independently of duration, a single (non-chord) note that is entirely
  string-muted or palm-muted is always eligible for truncation when either
  import preference is enabled, subject to the same bend/vibrato/slide
  exemption;
- because both of those duration-independent truncation branches require a
  single note rather than a chord, and EOF's own default disables the chord
  preference, no branch can truncate a chord under EOF's default preferences
  -- so the check evaluates each note independently (matching PyGuitarPro's
  per-note effect model) rather than reproducing EOF's per-beat aggregate
  note-effect bookkeeping across a chord's several strings, which only has an
  observable effect when the chord preference is explicitly enabled.

The Python implementation does not copy EOF's C source and does not bundle or
launch EOF. It does not yet evaluate whether generated/exported arrangement
output (as opposed to directly imported note data) respects the same
preferences; that remains unaudited and out of scope for this slice. A
previously suspected second gap -- a short note being exempted from
truncation solely because the *previous* note's legato/shift slide targets
it -- was investigated against `EOF_UPSTREAM_COMMIT` and does not exist:
`eof_load_gp`'s truncation-eligibility decision (`gp_import.c` lines
~4191-4218) runs per note, inside the per-beat note-creation loop, strictly
before the only two passes that walk the cross-beat note sequence ("Correct
slide directions" at ~4498 and "Convert slide in from above/below notation"
at ~4595), so neither can influence an already-finalized truncation
decision. `EOF_NOTE_TFLAG_SLIDE_IN` itself is set only from a note's own
"slide in from above/below" byte, never derived from a neighboring note's
shift/legato slide-to status. Only a slide notated directly on the note
itself, including "slide into this note from above/below", exempts it,
which this check already covers.

This check is advisory only: it reports whether the generator's directly
imported note sustains already collapse to EOF's default-preference result
(currently a known, unimplemented gap for essentially all EOF-truncatable
notes, since the generator does not yet apply this preference on import), and
never rewrites canonical chart state.

### Generated/exported arrangement output boundary adaptation

Issue #414's parity item B's remaining scope, after the explicit-rest and
short-note/staccato/mute truncation slices above, was whether generated/
exported arrangement output -- not just directly-imported note data -- still
respects the same boundaries once Bass reconciliation (`reconciliation.py`,
audio-vs-symbolic evidence) or Lead/Rhythm shared-score arrangement
materialization (`score_role_composition.py`) has run and projected each
source note onto promoted human-reviewed timing
(`reviewed_timing_transform.map_reviewed_source_time`).

`src/rocksmith_cdlc_generator/eof_export_boundary_check.py` does not re-audit
EOF: it imports and reuses `extract_explicit_rest_intervals` (from the
explicit-rest boundary adaptation above) and the newly-extracted
`eof_truncation_decision` function (factored out of
`eof_short_note_truncation_check.py`'s per-note decision without behavior
change) against `reviewed_export_events.reviewed_export_arrangement`'s
post-reconciliation/post-materialization notes -- the same read model every
Bass/Lead/Rhythm authoring path consumes on the way to the Rocksmith XML
boundary -- instead of the notes the importer would directly extract:

- every explicit rest interval is projected through the promoted reviewed
  timing map and checked against every materialized note's already-reviewed-
  time interval, so a reconciliation or timing-projection step that stretches
  a sustain across a rest respected at import time is caught;
- EOF's truncation decision is computed per registered-score note (from a
  fresh beat/note walk of the registered score, since the fan-out's own note
  representation does not carry the full-mute/staccato/tremolo/bend/vibrato/
  slide technique detail this decision needs) and matched to its materialized
  counterpart by source-relative onset time and pitch (MIDI) rather than
  string/fret, because Bass reconciliation may re-voice a note onto a
  different physical string/fret (`fret_mapping.py`) for the same pitch; the
  predicted post-truncation duration is itself projected through reviewed
  timing before being compared against the note's actual materialized
  sustain;
- a composed multi-track Lead/Rhythm arrangement is supported: every distinct
  literal contributing registered-score track is resolved, and each track's
  own explicit rests and truncation-eligible notes are checked only against
  the materialized notes that resolve back to that same literal track, never
  against another contributing track's unrelated passage, before results are
  pooled into one report; a materialized note whose contributing track is not
  among the arrangement's declared tracks fails closed rather than being
  silently ignored. A truncatable registered-score note that cannot be
  matched to exactly one materialized note on its own contributing track
  (expected for some Bass notes that reconciliation replaced or dropped in
  favor of audio evidence) is likewise reported rather than silently
  skipped.

The Python implementation does not copy EOF's C source and does not bundle or
launch EOF. It does not evaluate section/phrase boundary parity: this
project's Rocksmith authoring pipeline does not yet carry an EOF-comparable
section/phrase model to check against (see `docs/integrations/
EOF_PARITY_ROADMAP.md` roadmap item F).

This check is advisory only: it reports whether the generator's post-
reconciliation/post-materialization note sustains still respect EOF-derived
explicit-rest and short-note/staccato/mute truncation boundaries, and never
rewrites canonical chart, timing, or export authority.

### Note endpoint resnapping/rounding adaptation

`raynebc/editor-on-fire` `src/gp_import.c` (audited at the pinned commit
above), immediately before returning an imported Guitar Pro song, runs a
dedicated pass over every imported note. The comment at that exact call site
reads, verbatim: "Resnap the end positions of notes that end 1ms after a
grid snap position due to floating point math rounding error." For each
note, it computes the nearest "beat interval position" to the note's end (an
internal grid-snap helper, `eof_is_any_beat_interval_position()`); if the
note's end is not already exactly on that position, the nearest position was
found, it is later than the note's start, and the discrepancy is exactly
1ms, the note's length is corrected so its end lands exactly on the grid
position (any tech/bend-point note glued to the old end position moves with
it). This exists because GP's tick-based timing is converted to milliseconds
via floating-point math elsewhere in the same import pass, which can leave a
note's computed end exactly 1ms off the grid position it was actually meant
to land on.

`src/rocksmith_cdlc_generator/eof_note_endpoint_resnap_check.py` ports the
outer condition of that pass as an advisory check:
`compute_eof_note_endpoint_resnap_check()` flags any note in a canonical
`ImportedSource` (any adapter, not only Guitar Pro) whose end sits within
~1ms of an imported beat-grid position (`ImportedSource.beat_times_seconds`)
without landing on it.

`eof_is_any_beat_interval_position()`'s own definition was not located in
the accessible EOF source tree during this audit -- `src/gp_import.c`,
`src/song.c`, and `src/menu/beat.c` all call it but none of them define it.
This adaptation therefore does not assume any beat-grid resolution finer
than this project's own imported beat grid: the calling context in
`gp_import.c` is specifically about notes already positioned against that
same grid, so a ~1ms drift there is attributable to rounding against it,
independent of whatever finer subdivision the upstream helper may also
support for unrelated (non-import) EOF editing operations that were not
audited here.

The Python implementation does not copy EOF's C source and does not bundle
or launch EOF. Unlike EOF's own pass, it is advisory-only (report, not
auto-correct) and does not resnap a secondary tech/bend-point note store
(this project has none yet), consistent with every other EOF-derived check
above never silently rewriting canonical chart state.

### Pinch harmonic export attribute adaptation

`raynebc/editor-on-fire` `src/gp_import.c` (audited at the pinned commit
above) reads GP's raw harmonic-type byte for a note (1=natural,
2=artificial, 3=tapped, 4=pinch, 5=semi) and sets
`EOF_PRO_GUITAR_NOTE_FLAG_HARMONIC` only for type 1 (natural); every other
type sets `EOF_PRO_GUITAR_NOTE_FLAG_P_HARMONIC` instead, under the default
(disabled) value of the `eof_gp_import_nat_harmonics_only` preference
declared in `src/main.c`. `src/rs.c`'s Rocksmith XML export writes these as
two separate note attributes, `harmonic` and `harmonicPinch`
(`eof_conditionally_append_xml_long(..., "harmonic", tech.harmonic, 0)` and
the equivalent call for `tech.pinchharmonic` immediately after it).

This project's own PyGuitarPro dependency exposes the identical five-way
distinction directly in its parsed object model
(`NaturalHarmonic`/`ArtificialHarmonic`/`TappedHarmonic`/`PinchHarmonic`/
`SemiHarmonic`, each setting `HarmonicEffect.type` to 1-5 respectively --
confirmed by reading PyGuitarPro's own class definitions, matching GP's raw
byte convention exactly), but this project's importer previously collapsed
all five into one generic `"harmonic"` technique label, which
`rocksmith_xml.py` exported uniformly as the plain `harmonic="1"` attribute
-- including for pinch harmonics. This was an active correctness bug in
generated Rocksmith XML, not merely a missing-detail advisory: the existing
`_ARRANGEMENT_PROPERTY_NAMES` list already declared a `pinchHarmonics`
arrangement property, but nothing ever populated it.

`guitarpro_import.py`'s `_techniques()` now tags only natural harmonics as
`"harmonic"`; every other GP harmonic type is tagged `"harmonic_pinch"`
instead (added to `reviewed_techniques.SUPPORTED_TECHNIQUES` and
`rocksmith_xml.DIRECT_NOTE_TECHNIQUES` so it flows through review and export
like any other supported technique, rather than being silently filtered or
rejected). `rocksmith_xml.py` emits the `harmonicPinch` note attribute (not
`harmonic`) for it, and sets the arrangement-level `pinchHarmonics` property
alongside the existing `harmonics` property.

The Python implementation does not copy EOF's C source and does not bundle
or launch EOF.

### Exact tie-continuation behavior

The reviewed-authoring tie-folding slice inspected current upstream
`src/gp_import.c` at `98753f56ec655e86bd1d753d4e1e30002a94e151`, including
the multi-string tie-extension correction at
`55b6a01896870454dabef588571386842ad8abe0` and the current
different-string behavior after `52268943ad5731c3a567c1c40d605ee3d8bd98b1`.
The implementation is a narrower clean adaptation rather than copied C source: only
tie-only, exact-adjacency, same-string/fret/pitch continuations fold, and source-event
lineage plus the project's stronger trust/review gates remain authoritative.

### Fork classification note

`xmist001/editor-on-fire-automated` was initially surfaced as a possible automation-oriented fork. A deeper repository audit established that it is a direct fork/snapshot of `raynebc/editor-on-fire`; its `master` head is upstream commit `a6b81a4edad6f5b48bd455e98111b56fc007a49d` from 2026-05-21, and that exact commit exists in the primary repository. The May 2026 GP/timing/COUNT changes first noticed through that repository are therefore upstream EOF work, not proven fork-specific automation features.

The repository name alone must not be treated as evidence of a separate automated implementation. It remains a historical snapshot unless unique divergence is later demonstrated.

### Reuse policy

This project's Python implementation is not a bundled copy of the EOF application. Relevant deterministic authoring behavior may be studied, ported, adapted or directly reused when the file-level licensing permits it and doing so is preferable to independently reimplementing mature behavior.

For substantial direct adaptations, record the upstream repository/path and preferably the source commit/SHA in the implementation PR or source documentation. Preserve required BSD attribution and conditions.

The standing audit/reuse plan is documented in:

- `docs/eof-reference-parity-program.md`
- `docs/eof-subsystem-parity-matrix.md`
- `docs/eof-upstream-fork-inventory.md`
- `docs/eof-automated-comparison.md`

Before directly reusing code from any third-party subtree bundled inside EOF, review that subtree's own license separately. This notice applies to EOF project code under its root license; it does not automatically cover every vendored dependency.

## Rocksmith Custom Song Toolkit and adjacent tools

`rscustom/rocksmith-custom-song-toolkit` and relevant forks are reference sources for Rocksmith XML, SNG, package and dynamic-difficulty behavior under issue #414.

Their code is **not** covered by EOF's BSD license merely because it participates in the same authoring ecosystem. Inspect the applicable project/file licenses before any direct code reuse. Until that audit is complete, treat toolkit/DDC source as behavior/design reference material rather than an automatically reusable donor codebase.
