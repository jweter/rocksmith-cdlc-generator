# EOF Subsystem Parity Matrix

Issue: #414  
Program: `docs/eof-reference-parity-program.md`

## How to use this matrix

This is the working comparison ledger between Rocksmith CDLC Generator and mature reference implementations, primarily Editor on Fire (EOF).

Status values:

- **UNASSESSED** — reference behavior not yet traced.
- **PARTIAL** — some behavior exists in both systems but parity is not established.
- **PARITY** — relevant behavior is intentionally equivalent and regression-protected.
- **PARITY+** — EOF-compatible baseline is preserved and this project deliberately extends it.
- **DIVERGENT** — behavior intentionally differs for a documented reason.
- **GAP** — mature behavior exists and this project is missing or materially wrong.
- **N/A** — not applicable to this project's product path.

Reuse values:

- **study** — use as design/behavior reference only.
- **port** — translate/adapt algorithm into this project's architecture.
- **direct** — direct/substantial code reuse is appropriate after file-level license review and attribution.
- **retain** — our existing implementation is preferable; use reference only for regression ideas.

Every completed row should eventually include concrete upstream path/commit evidence and a test/issue/PR reference.

## A. Guitar Pro parsing and symbolic timing

| Subsystem | Primary EOF reference | Our likely/current area | Status | Reuse | Priority | Notes / exit condition |
|---|---|---|---|---|---|---|
| GP3/GP4/GP5 binary parsing | `src/gp_import.c/.h` | `guitarpro_import.py`, source import | PARTIAL | port/direct | P0 | Compare version quirks, track data, durations, techniques and recovery semantics. |
| GP measure/time-signature model | `src/gp_import.c`, beat helpers | `guitarpro_import.py`, `source_import.py` | PARTIAL | port | P0 | Confirm measure positions survive import without hidden offsets. |
| Tempo events | `src/gp_import.c`, `src/beat.c/.h` | imported tempo events, `beats.py` | PARTIAL | port | P0 | Same GP must produce semantically equivalent source beat clock. |
| Explicit beat grid | `src/beat.c/.h` | `ImportedSource.beat_times_seconds` | PARTIAL | port | P0 | Compare rounding, anchors and beat-unit handling. |
| Leading rests/count-in/pre-roll | GP/GPA timing paths | `alignment.py`, onset refinement | PARITY | port | P0 | PR #413 adopted pre-zero handling; continue real packaged verification. |
| Chart delay / non-zero first beat | GP/GPA/project timing | alignment/project model | PARTIAL | port | P0 | Audit EOF cases where first beat is not 0 s. |
| GPA sync-point behavior | `src/gp_import.c/.h` | score→recording alignment | PARTIAL | port | P0 | Trace sync-point-to-project-beat semantics and edge cases. |
| Repeat unwrapping | `eof_unwrap_gp_track()` and helpers | `eof_repeat_unfolding.py` | PARTIAL | port | P0 | Advisory realized-sequence comparison landed (#462); the importer itself still does not unfold repeats (written score order only). |
| Alternate endings | GP measure/unwrapping logic | `eof_repeat_unfolding.py` | PARTIAL | port | P0 | Bitmask alternate-ending realization covered by the same #462 check; Da Capo/Segno/Coda/Fine navigation symbols remain explicitly out of scope (no normalized table in PyGuitarPro's object model). |
| Coda/segno/fine navigation | GP musical-symbol logic | source import | UNASSESSED | port | P1 | Required for complex scores. |
| Triplet feel | current upstream GP import logic | source import | UNASSESSED | port | P1 | Upstream rewrote this in May 2026; audit current `raynebc` implementation, not the `xmist001` snapshot. |
| Tied notes | GP import logic | source note construction + reviewed authoring | PARTIAL | port | P0 | Exact same-string/fret/pitch tie-only chains now fold at the reviewed Bass/Lead/Rhythm authoring boundary with continuation lineage, dual-clock adjacency, and composed source-track scoping. Different-string, mixed-technique, ambiguous, gap, overlap and linked-note behavior remain to audit. |
| Staccato/short-note truncation | `eof_load_gp()` note_is_short/truncate logic, `src/main.c` preference defaults | `eof_short_note_truncation_check.py`, `eof_export_boundary_check.py` | PARTIAL | port | P0 | Advisory check reproduces EOF's default-preference truncation decision (duration/staccato/mute/palm-mute, technique exemptions) and compares it to the generator's currently-untruncated imported sustains; the importer itself still does not apply truncation. `eof_export_boundary_check.py` re-applies the same decision against post-reconciliation/post-materialization notes, including a composed multi-track Lead/Rhythm arrangement (each contributing track's own facts matched only against notes resolved back to that same literal track), so a defect introduced after import, not just at import, is now covered too. A previously suspected previous-note legato/shift slide-in exemption was investigated against the pinned upstream commit and does not exist in EOF's import-time truncation decision. |
| Note endpoint resnapping/rounding | `gp_import.c` note-tail resnap pass (verbatim comment: "Resnap the end positions of notes that end 1ms after a grid snap position due to floating point math rounding error") | `eof_note_endpoint_resnap_check.py` | PARTIAL | port | P0 | Advisory check flags an imported note whose end sits within ~1ms of an imported beat-grid position without landing on it (the same narrow condition EOF's own pass corrects for). EOF's internal grid-snap helper (`eof_is_any_beat_interval_position`) was called from `gp_import.c`, `song.c`, and `src/menu/beat.c` but its own definition was not located in the accessible source tree; this check therefore compares against this project's own imported beat grid rather than assuming a finer EOF-internal subdivision. Advisory only (report, not auto-correct), consistent with this project's provenance/review-first checks. |
| Invalid GP notation recovery | EOF import guards | parser validation | UNASSESSED | port | P1 | Fail safely on malformed/GP-newer-version quirks rather than inventing data. |

## B. Score-to-recording timing and authority

| Subsystem | Primary reference | Our area | Status | Reuse | Priority | Notes / exit condition |
|---|---|---|---|---|---|---|
| Project beat map as timing authority | EOF beat/project model | `alignment.py`, `shared_timeline.py` | PARTIAL | port | P0 | Same GP/audio must map notes once, not double-count intro/offset. |
| Pre-zero synchronized score beats | EOF GPA import | onset refinement | PARITY | port | P0 | Regression added in #413. |
| Global translation correction | EOF sync behavior + our audio evidence | onset refinement | PARITY+ | retain/port | P0 | EOF semantics plus evidence-driven automation. |
| Source timing qualification | no direct EOF equivalent | `source_timing_qualification.py` | PARITY+ | retain | P0 | Our stronger fail-closed gate remains. |
| Beat-grid validation | EOF tempo-map validation | tempo map + alignment | UNASSESSED | port | P0 | Compare automated error detection/correction rules. |
| Timing edits preserving anchors | EOF beat editing | reviewed timing workspace | PARTIAL | study/port | P1 | Compare invariant handling, not GUI mechanics. |
| Same timing authority for B/L/R | EOF project model / our architecture | shared timeline | PARITY+ | retain | P0 | Our single reviewed authority is deliberate architecture. |

## C. Note duration, gaps and sustain semantics

| Subsystem | EOF reference | Our area | Status | Reuse | Priority | Notes |
|---|---|---|---|---|---|---|
| Basic note duration | GP import + song model | imported note duration | PARTIAL | port | P0 | Reviewed authoring now preserves exact folded tie-chain endpoints; broader GP duration/staccato parity remains. |
| Required inter-note gap | EOF note-gap/crazy status logic | arrangement generation/export | UNASSESSED | port | P0 | Relevant to silent-gap sustain defect class. |
| Sustain to next note | EOF note/end logic | preview/export | UNASSESSED | port | P0 | Must not create sustain through intended silence. |
| Crazy/no-gap exception | EOF special status | internal technique/model | UNASSESSED | study/port | P1 | Determine Rocksmith relevance before adopting. |
| Chord duration/truncation | recent GP import fixes | chord/event model | UNASSESSED | port | P0 | Compare staccato and tied chord behavior. |
| Explicit rest boundary integrity | `eof_load_gp()` rest-beat-type byte | `eof_rest_boundary_check.py`, `eof_export_boundary_check.py` | PARTIAL | study | P0 | Advisory check cross-references every explicit-rest beat against imported note intervals for overlap; short-note/staccato/mute truncation is separately covered by `eof_short_note_truncation_check.py` (see "Staccato/short-note truncation" above). `eof_export_boundary_check.py` projects the same explicit-rest intervals through promoted reviewed timing and checks them against post-reconciliation/post-materialization notes, including a composed multi-track Lead/Rhythm arrangement (each contributing track's own rests checked only against notes resolved back to that same literal track), so a reconciliation/timing-projection step that stretches a sustain across a rest is now covered too; section-boundary parity remains unaudited (see roadmap item F). |

## D. Techniques

| Technique | EOF reference | Our area | Status | Reuse | Priority | Notes |
|---|---|---|---|---|---|---|
| Hammer-on / pull-off | GP import + RS export | technique model | PARTIAL | port | P1 | Compare source flags and Rocksmith output. |
| Tap | GP import / RS | technique model | PARTIAL | port | P1 | Validate note/chord semantics. |
| Palm mute | GP import / RS | technique model | PARTIAL | port | P1 | Preserve per-note/string semantics. |
| Harmonic / pinch harmonic | GP import / RS | technique model | UNASSESSED | port | P1 | Separate supported Rocksmith forms. |
| Tremolo picking | GP import / RS phrase logic | technique model | UNASSESSED | port | P1 | Include phrase boundaries where required. |
| Vibrato | GP import / RS | technique model | UNASSESSED | port | P1 | Compare intensity/boolean reduction semantics. |
| Bend strength | `rs.c`, GP bend parsing | technique model | PARTIAL | port/direct | P0 | Trace quarter-step/cents conversion and export. |
| Bend curve points | GP bend structures / RS | technique model | UNASSESSED | port | P1 | Determine fidelity needed for RS2014. |
| Slide in from above/below | PyGuitarPro `guitarpro.models.SlideType` (`intoFromAbove`/`intoFromBelow`) | `guitarpro_import.py:_slide_kinds()`, `SourceNoteEvent.slide_kinds` | PARTIAL | port | P0 | Import-side data preservation lands: all six PyGuitarPro `SlideType` subtypes (two "into", two "out", shift, legato) are now captured per-note in an additive `slide_kinds` field instead of being collapsed into one generic `"slide"` technique flag. That generic flag is kept unchanged (existing validation in `eof_rocksmith_validation.py`/`reviewed_techniques.py` already depends on its exact string), so `slide_kinds` is a separate, additive field rather than a `techniques` label to avoid tripping the `SUPPORTED_TECHNIQUES` whitelist those modules enforce. Remaining scope: resolving each pitched slide's target fret (GP encodes this implicitly as the next same-string note, not as an explicit value PyGuitarPro exposes) and Rocksmith XML export (`slideTo`/`unpitchSlideTo` attributes). |
| Pitched slide | GP + RS | technique model | PARTIAL | port | P0 | Subtype now captured (see row above); end-fret resolution and export semantics remain open. |
| Unpitched slide | GP + RS | technique model | PARTIAL | port | P0 | Subtype now captured (see row above); export semantics remain open. |
| Shift vs legato slide | PyGuitarPro `SlideType.shiftSlideTo`/`legatoSlideTo` | `guitarpro_import.py:_slide_kinds()` | PARTIAL | port | P1 | Both subtypes are now distinguished at import via `slide_kinds`; no heuristic needed since PyGuitarPro's own parsed model already carries the distinction explicitly. |
| Link-next | EOF RS semantics | technique model | UNASSESSED | port | P1 | Needed for slide/sustain semantics. |
| Ghost notes | GP import preferences | note model | UNASSESSED | port | P1 | Compare guitar/bass treatment. |
| Muted/string-muted notes | RS/fingering logic | note model | PARTIAL | port | P1 | Interacts with fingering/FHP. |

## E. Tuning, strings and position

| Subsystem | EOF reference | Our area | Status | Reuse | Priority | Notes |
|---|---|---|---|---|---|---|
| Track tuning import | GP import/tuning helpers | source track tuning | PARTIAL | port | P0 | Compare string order and pitch interpretation. |
| Capo | GP/track model | source/arrangement model | UNASSESSED | port | P1 | Ensure fret/pitch output remains consistent. |
| String index preservation | GP import | source note | PARTIAL | port | P0 | Never silently remap when explicit source position exists. |
| Fret preservation | GP import | source note | PARTIAL | port | P0 | Same as above. |
| 7-string/extended range handling | EOF GP logic | importer | UNASSESSED | study/port | P2 | Decide RS2014 supported reduction policy explicitly. |

## F. Chords, fingering, FHP and handshapes

| Subsystem | EOF reference | Our area | Status | Reuse | Priority | Notes |
|---|---|---|---|---|---|---|
| Chord template parsing/import | `src/rs_import.c` | chord identity/model | PARTIAL | port/direct | P0 | EOF parses Rocksmith finger/fret templates; useful oracle. |
| Chord identity | RS/chord helpers | reviewed chord identity | PARTIAL | port | P0 | Compare membership/name/shape semantics. |
| Fingering inference | `src/bf.c/.h`, RS helpers | fret mapping/review | PARTIAL | port/direct | P0 | High human-editing leverage. |
| Fingering validation | EOF fingering view/RS warnings | validation/review | UNASSESSED | port | P0 | Preserve stronger human authority around inference. |
| Fingerless/muted rules | recent EOF changes | fingering model | UNASSESSED | port | P1 | Avoid unnecessary review requirements. |
| Fret-hand positions | `src/rs.c`, song/track helpers | arrangement authoring | PARTIAL | port/direct | P0 | Audit placement, width, violations and generation. |
| FHP range/width | EOF fret-range tolerance logic | FHP model | UNASSESSED | port | P0 | Mature playability rules likely valuable. |
| Handshape/arpeggio phrases | RS/song/track logic | arrangement phrases | PARTIAL | port | P0 | Include chord-slide transitions. |
| Handshape/FHP violations | EOF RS panel checks | validation | UNASSESSED | port | P0 | Convert mature warnings into deterministic validation findings. |

## G. Phrases, sections and Rocksmith events

| Subsystem | EOF reference | Our area | Status | Reuse | Priority | Notes |
|---|---|---|---|---|---|---|
| Rocksmith section vocabulary | `src/rs.c` predefined sections | section model | PARTIAL | direct/port | P1 | EOF has explicit canonical section set. |
| Phrase boundaries | beat/RS helpers | phrase model | PARTIAL | port | P1 | Compare edge constraints and repetition semantics. |
| COUNT phrase / leading count measure | current EOF leading-silence + RS logic | not fully automated | UNASSESSED | port | P1 | May 2026 implementation is upstream EOF behavior; audit current upstream. |
| Tick events | EOF leading silence/RS events | event model | UNASSESSED | port | P2 | Needed if downstream RS semantics require. |
| Tremolo phrases | EOF RS logic | technique/phrase model | UNASSESSED | port | P1 | Compare generation/export. |
| Handshape phrases | EOF RS logic | handshape model | PARTIAL | port | P0 | See chord/FHP phase. |
| Section validation | EOF warnings | validation | UNASSESSED | port | P1 | Convert warnings into deterministic checks. |

## H. Difficulty and dynamic difficulty

| Subsystem | Reference | Our area | Status | Reuse | Priority | Notes |
|---|---|---|---|---|---|---|
| Static difficulty populations | EOF track difficulties | arrangement model | UNASSESSED | study/port | P2 | Understand before generating levels. |
| Difficulty tabs/population semantics | EOF | desktop model | N/A/learn | study | P3 | GUI mechanics not required; domain state may matter. |
| Dynamic difficulty generation | Rocksmith Custom Song Toolkit DDC | future DD | UNASSESSED | study/port/direct after license audit | P1 | Audit `RocksmithTookitGUI/DDC`, `DLCPackage/DDCreator.cs`, configs. |
| Chord protection/removal rules | toolkit DDC configs | future DD | UNASSESSED | study/port | P2 | Evaluate intended learning progression. |

## I. Rocksmith XML import/export and validation

| Subsystem | Reference | Our area | Status | Reuse | Priority | Notes |
|---|---|---|---|---|---|---|
| RS2014 XML import | EOF `src/rs_import.c` | import/reference tools | UNASSESSED | port/direct | P2 | Useful as oracle and round-trip fixture source. |
| RS2014 section/event export | EOF `src/rs.c` | XML authoring | PARTIAL | port/direct | P0 | Compare semantic output. |
| Chord templates | EOF + toolkit `Song2014.cs` | XML authoring | PARTIAL | port | P0 | High-value parity target. |
| Notes/chords XML fields | EOF + toolkit XML model | XML authoring | PARTIAL | port | P0 | Differential semantic tests. |
| Arrangement metadata | EOF RS arrangement model + toolkit | XML/package model | PARTIAL | port | P1 | Lead/Rhythm/Bass metadata must match RS expectations. |
| Phrase iterations/levels | toolkit XML model/DDC | XML authoring | UNASSESSED | port | P1 | Needed before robust dynamic difficulty. |
| Export warnings/validation | EOF RS checks | validation | PARTIAL | port | P0 | Mature warning rules should become deterministic blockers/warnings. |
| Tempo warning thresholds | EOF RS export | validation | UNASSESSED | study | P2 | Decide which are RS constraints vs editor convenience. |

## J. SNG, package and downstream tooling

| Subsystem | Reference | Our area | Status | Reuse | Priority | Notes |
|---|---|---|---|---|---|---|
| SNG2014 writing | toolkit `Sng2014FileWriter.cs` | PSARC/SNG bridge | PARTIAL | study/port subject to license | P1 | Compare structures with existing bridge; do not replace blindly. |
| Arrangement package model | toolkit `DLCPackage/Arrangement.cs` | package model | PARTIAL | study | P1 | Check metadata/IDs/relationships. |
| Aggregate graph | toolkit `AggregateGraph2014` | package generation | UNASSESSED | study | P2 | Audit only if relevant to our bridge. |
| DDC invocation/config | toolkit DDC | future DD/build | UNASSESSED | study/port | P1 | Establish behavior and licensing. |
| Toolkit external app integration | toolkit | DLC Builder handoff | PARTIAL | study | P2 | Learn resilient discovery/handoff patterns. |

## K. Product/UX concepts worth learning but not porting wholesale

| Area | Reference value | Decision |
|---|---|---|
| Piano-roll editor | Mature visual debugging of note/beat relationships | LEARN ONLY; our UI remains modern Windows authoring workspace. |
| FHP/fingering visualization | Clear explanation of playability violations | PARITY+ opportunity; adopt concepts with our design system. |
| Rocksmith status panels | Mature warnings close to authoring context | PARITY+ opportunity; map to our project health/validation surfaces. |
| Manual beat editing | Excellent reference for invariants | LEARN ONLY; our automation/review model remains different. |
| Undo/redo mutable editor state | Useful behavior reference | INTENTIONAL DIVERGENCE; retain transactional provenance-aware review state. |

## First audit sequence

The next detailed audit should proceed in this order:

1. GP import + source beat clock.
2. note duration/gap/sustain semantics.
3. repeats/ties/alternate endings/triplet feel.
4. slide and bend semantics.
5. chord/fingering/FHP/handshape.
6. Rocksmith phrase/section/event validation.
7. XML semantic differential tests.
8. toolkit/DDC/package comparison.

Do not start with broad GUI imitation. The value is in deterministic domain correctness first.

## Fork evidence rule

A fork is referenced as a distinct implementation only after commit/branch comparison proves unique behavior. `xmist001/editor-on-fire-automated` is currently a May 2026 snapshot of primary EOF, not a separate automated lineage.
