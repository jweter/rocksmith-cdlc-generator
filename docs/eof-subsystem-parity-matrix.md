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
| Required inter-note gap | EOF note-gap/crazy status logic | arrangement generation/export | PARTIAL | port | P0 | `eof_note_gap_check.py` ports `song.c`'s `eof_get_note_max_length()` hard ceiling (a note's sustain may never extend past the position of the next note sharing its lane/string, LINKNEXT included) as an advisory check over `ReviewedExportArrangement` -- the post-reconciliation/post-materialization read model every export path consumes. Cross-string overlap (chords) and tied continuation notes (`techniques` contains `"tie"`) are deliberately excluded, not flagged. Advisory only; the importer/authoring pipeline itself does not yet enforce this ceiling. |
| Sustain to next note | EOF note/end logic | preview/export | PARTIAL | port | P0 | Same `eof_note_gap_check.py` check covers this: an overlapping same-string sustain would otherwise sound through what should be the next note's own attack. Must not create sustain through intended silence -- see also `eof_rest_boundary_check.py`/`eof_export_boundary_check.py` for the explicit-rest case, which this check does not evaluate. |
| Crazy/no-gap exception | EOF special status | internal technique/model | UNASSESSED | study/port | P1 | Determine Rocksmith relevance before adopting. |
| Chord duration/truncation | recent GP import fixes | chord/event model | UNASSESSED | port | P0 | Compare staccato and tied chord behavior. |
| Explicit rest boundary integrity | `eof_load_gp()` rest-beat-type byte | `eof_rest_boundary_check.py`, `eof_export_boundary_check.py` | PARTIAL | study | P0 | Advisory check cross-references every explicit-rest beat against imported note intervals for overlap; short-note/staccato/mute truncation is separately covered by `eof_short_note_truncation_check.py` (see "Staccato/short-note truncation" above). `eof_export_boundary_check.py` projects the same explicit-rest intervals through promoted reviewed timing and checks them against post-reconciliation/post-materialization notes, including a composed multi-track Lead/Rhythm arrangement (each contributing track's own rests checked only against notes resolved back to that same literal track), so a reconciliation/timing-projection step that stretches a sustain across a rest is now covered too; section-boundary parity remains unaudited (see roadmap item F). |

## D. Techniques

| Technique | EOF reference | Our area | Status | Reuse | Priority | Notes |
|---|---|---|---|---|---|---|
| Hammer-on / pull-off | `src/gp_import.c` (`eof_load_gp()`: a single raw GP hammer/pull-off byte on the destination note; direction resolved by comparing that note's fret (`endfret`) to the immediately preceding same-string note's fret (`startfret`) -- higher sets `EOF_PRO_GUITAR_NOTE_FLAG_HO`, lower sets `EOF_PRO_GUITAR_NOTE_FLAG_PO`, audited at commit `c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100`); `src/rs.c` (exports separate `hammerOn`/`pullOff` note/chordNote XML attributes and sets the arrangement-level `hopo` property when either flag is present anywhere in the track) | `guitarpro_import.py:_resolve_hammer_pulloff_direction()`, `musicxml_import.py:_techniques()` (MusicXML already exposes explicit `<hammer-on>`/`<pull-off>` notations with no direction ambiguity), `rocksmith_xml.py` (`DIRECT_NOTE_TECHNIQUES`, `_technique_attributes()`, `hopo` arrangement property) | PARITY | port | P1 | Guitar Pro exposes only one ambiguous `NoteEffect.hammer` bit (`_techniques()`'s prior generic `"hammer_on_pull_off"` label); `_resolve_hammer_pulloff_direction()` now resolves it into the specific `"hammer_on"`/`"pull_off"` labels the MusicXML importer already emitted directly, using the identical previous-same-string-note fret comparison EOF's own GP import performs. A note with no preceding same-string note, or an equal fret, is left as the generic `"hammer_on_pull_off"` label and continues to fail closed at the Rocksmith XML export boundary, matching the unresolved-slide/bend pattern. Both importers' resolved labels now export as real `hammerOn="1"`/`pullOff="1"` note attributes plus the `hopo` arrangement property for Bass, Lead, and Rhythm, instead of failing the entire reviewed-authoring handoff (`ValueError: ... not losslessly supported yet`) as before -- this was a severe correctness gap, not a cosmetic one, since virtually every guitar/bass tab contains hammer-ons/pull-offs. Not yet packaged-verified against real Rocksmith import/playback. Tap (a distinct GP effect) remains separate and unaudited -- see the "Tap" row below. |
| Tap | GP import / RS | technique model | PARTIAL | port | P1 | Validate note/chord semantics. |
| Palm mute | GP import / RS | technique model | PARTIAL | port | P1 | Preserve per-note/string semantics. |
| Harmonic / pinch harmonic | `gp_import.c` (harmonic-type byte 1=natural/2=artificial/3=tapped/4=pinch/5=semi, matched 1:1 to PyGuitarPro's `HarmonicEffect.type`; only type 1 sets `EOF_PRO_GUITAR_NOTE_FLAG_HARMONIC`, all others set `EOF_PRO_GUITAR_NOTE_FLAG_P_HARMONIC` under `eof_gp_import_nat_harmonics_only`'s default-off value in `main.c`), `rs.c` (exports separate `harmonic`/`harmonicPinch` XML attributes) | `guitarpro_import.py:_techniques()`, `rocksmith_xml.py` | GAP fixed | port | P1 | This was an active correctness bug, not just a missing-detail warning: every harmonic type (including pinch/artificial/tapped/semi) was previously exported as the plain `harmonic="1"` XML attribute, and `_ARRANGEMENT_PROPERTY_NAMES`'s existing `pinchHarmonics` property was never populated. Now: `_techniques()` tags only natural harmonics as `"harmonic"` and everything else as a new `"harmonic_pinch"` label (added to `reviewed_techniques.SUPPORTED_TECHNIQUES` and `rocksmith_xml.DIRECT_NOTE_TECHNIQUES`); `rocksmith_xml.py` emits the `harmonicPinch` note attribute and sets the `pinchHarmonics` arrangement property for it. |
| Tremolo picking | GP import / RS phrase logic | technique model | UNASSESSED | port | P1 | Include phrase boundaries where required. |
| Vibrato | GP import / RS | technique model | UNASSESSED | port | P1 | Compare intensity/boolean reduction semantics. |
| Bend strength | `rs.c` (RS XML export: `step` attribute = quarter-step count / 2.0, i.e. semitones); PyGuitarPro's own GP decoding (`gp3.py:readBend`, already normalizes raw GP bytes to `BendPoint.position` 0..12 and `.value` in whole semitones, `bendSemitone=25`/`bendPosition=60`); public RS2014 XML `<note bend="1"><bendValues count="N"><bendValue time="..." step="..."/></bendValues></note>` schema (corroborated against `rscustom/rocksmith-custom-song-toolkit`'s community-documented Song2014 XML model; the `rs.c` excerpts inspected did not show the RS2 note-level XML serialization directly, only RS1-era `bendstrength` fields) | `guitarpro_import.py:_bend_points()`, `source_import.SourceBendPoint`, `rocksmith_xml.py` (`note_has_exportable_bend_curve`, `_bend_values`, `_append_bend_values`), `reviewed_export_events.py`/`reviewed_guitar_authoring.py`/`reviewed_bass_authoring.py`/`reviewed_rocksmith_xml.py`/`reviewed_rocksmith_xml_render.py` (additive `bend_points` field threaded through every reviewed-authority layer), `eof_rocksmith_validation.py` (`has_exportable_bend_curve` suppresses `rocksmith_bend_detail_missing` once the curve is actually exported) | PARITY | port | P0 | Full remaining scope from the previous entry landed: the captured curve now threads through every layer of the current reviewed-authority pipeline (`ReviewedExportNote` -> `ReviewedGuitarAuthoringNote`/`ReviewedBassAuthoringNote` -> `ReviewedRocksmithXmlNote` -> `GuitarAuthoringNote`/`MappedNote`) and is emitted as real `<bendValues>`/`<bendValue>` elements in `build_rocksmith_guitar_xml`/`build_rocksmith_bass_xml` (single notes and chord notes). `bend` is treated as exportable in `DIRECT_NOTE_TECHNIQUES`-gated checks only when the note actually carries curve points (`note_has_exportable_bend_curve`); a `"bend"` technique label with no captured points (e.g. from MusicXML/PSARC re-import, or a manual technique edit) still fails closed exactly as before, so no strength is ever invented. Verified with unit and end-to-end tests (`test_rocksmith_xml.py`, `test_guitar_rocksmith_xml.py`, `test_reviewed_rocksmith_xml.py`, `test_reviewed_rocksmith_xml_render.py`, `test_reviewed_guitar_authoring.py`, `test_reviewed_bass_authoring.py`, `test_eof_rocksmith_validation.py`); not yet verified against a real packaged Rocksmith import/playback (Product Reality evidence remains open -- see the "Bend timing" note below and the standing packaged-verification gate this repo tracks for all new authoring behavior). The legacy non-reviewed `guitar_authoring.build_guitar_authoring_chart` chart-building path and the audio-driven `fret_mapping.map_reconciled_bass_chart` reconciliation path were deliberately left out of scope: they are not the current reviewed-authority XML pipeline `reviewed_rocksmith_xml_render.py` calls, and a note reaching Rocksmith XML through either of them still carries no bend curve data (`bend_points` defaults to empty), so behavior there is unchanged, not regressed. Bend timing note: community documentation of adjacent toolkits describes a common one-third-of-sustain placement convention used when a tool lacks per-point data; this project has real per-point data from PyGuitarPro's own parsed curve, so `_bend_values()` uses each point's actual `position` fraction instead of that fallback heuristic. |
| Bend curve points | GP bend structures / RS | technique model | PARITY | port | P1 | Same landed change as the "Bend strength" row above; the two rows describe the same curve-fidelity work and could be merged in a future pass. |
| Slide in from above/below | `src/gp_import.c` reads the GP slide-type byte but discards it (no EOF import-side mapping exists, confirmed at commit `c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100`); PyGuitarPro `guitarpro.models.SlideType` (`intoFromAbove`/`intoFromBelow`) used instead | `guitarpro_import.py:_slide_kinds()`, `SourceNoteEvent.slide_kinds` | PARTIAL | study | P0 | Import-side data preservation landed (all six PyGuitarPro subtypes captured in `slide_kinds`); this row covers only the target-less "into"/"out" subtypes (`intoFromAbove`/`intoFromBelow`/`outDownwards`/`outUpwards`), which have no defined destination fret to resolve or export -- see the "Pitched slide"/"Unpitched slide" rows below for the two subtypes ("shift"/"legato") that do. EOF audit finding unchanged: `gp_import.c` never maps the GP slide-type byte to any note flag (log-only), so there is no EOF import-time behavior to port here. |
| Pitched slide | `src/rs.c` (RS XML export: `slideTo` attribute = destination fret); `src/rs_import.c` populates `EOF_PRO_GUITAR_NOTE_FLAG_SLIDE_UP`/`_SLIDE_DOWN` from RS XML's `slideTo` on re-import (this project's own `psarc_import.py` already reads the same `slideTo` attribute on re-import, corroborating the attribute name/shape); PyGuitarPro `SlideType.shiftSlideTo`/`legatoSlideTo` used for import-side subtype capture | `guitarpro_import.py:_resolve_slide_target_frets()`, `source_import.SourceNoteEvent.slide_target_fret`/`link_next`, `rocksmith_xml.py` (`note_has_exportable_slide_target`, `slideTo`/`linkNext` attributes in `_technique_attributes`), `reviewed_export_events.py`/`reviewed_guitar_authoring.py`/`reviewed_bass_authoring.py`/`reviewed_rocksmith_xml.py`/`reviewed_rocksmith_xml_render.py` (additive `slide_target_fret`/`link_next` fields threaded through every reviewed-authority layer, mirroring `bend_points`), `eof_rocksmith_validation.py` (`has_exportable_slide_target` suppresses `rocksmith_slide_detail_missing` once the target is actually exported) | PARITY | port | P0 | The "shift"/"legato" pitched-slide subtypes now resolve their implicit Guitar Pro destination (GP encodes it only as "the next note on this string", not as an explicit value PyGuitarPro exposes) and export it losslessly as the Rocksmith XML `slideTo` attribute plus the `slides` arrangement property, threaded through every layer of the reviewed-authority pipeline exactly like the bend-curve work above. A slide note with no later same-string note to resolve against (e.g. the last note on that string) is left unresolved and continues to fail closed (`rocksmith_slide_detail_missing`), same as an unresolved bend. Verified with unit tests (`test_guitarpro_import.py`, `test_rocksmith_xml.py`, `test_reviewed_rocksmith_xml.py`, `test_reviewed_export_events.py`, `test_reviewed_guitar_authoring.py`, `test_eof_rocksmith_validation.py`); not yet verified against a real packaged Rocksmith import/playback (Product Reality evidence remains open, per the standing packaged-verification gate this repo tracks for all new authoring behavior). Correction to a prior version of this row: link-next state *is* a separate RS XML attribute (`linkNext`), and EOF's own `gp_import.c` (audited at commit `c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100`) maps only the "legato" pitched-slide subtype's GP slide-type bit to `EOF_PRO_GUITAR_NOTE_FLAG_LINKNEXT` -- a "shift" slide never sets it. This was a genuine gap (every resolved pitched slide exported identically regardless of subtype, silently dropping the legato/shift distinction Rocksmith actually encodes) fixed in the same family as the harmonic-type fix above: a resolved "legato" slide now also sets the new additive `link_next` field, exported as `linkNext="1"` alongside `slideTo`; a resolved "shift" slide never does. Direction (up/down) is still not a separate RS XML attribute and remains out of scope. |
| Unpitched slide | GP + RS | technique model | PARTIAL | port | P0 | Subtype captured at import (see "Slide in from above/below" row); the `outDownwards`/`outUpwards` subtypes have no PyGuitarPro-exposed target fret to resolve (unlike shift/legato above) and remain unresolved/unexported -- `slide_target_fret` stays unset and export continues to fail closed via `rocksmith_slide_detail_missing`. |
| Shift vs legato slide | PyGuitarPro `SlideType.shiftSlideTo`/`legatoSlideTo`; `src/gp_import.c` maps only the legato bit to `EOF_PRO_GUITAR_NOTE_FLAG_LINKNEXT` | `guitarpro_import.py:_slide_kinds()`, `_resolve_slide_target_frets()` | PARITY | port | P1 | Both subtypes are distinguished at import via `slide_kinds`, and both now resolve/export the same `slideTo` value (see "Pitched slide" row above) -- but they are no longer exported identically: a resolved legato slide additionally sets `link_next`/`linkNext="1"`, a resolved shift slide does not, matching EOF's own GP-import behavior exactly (see "Link-next" row and the "Pitched slide" row's correction note). |
| Link-next | `src/rs.c` (`eof_rs2_export_note_string_to_xml()` emits the `linkNext` note/chordNote attribute from `tech.linknext`, itself read from `EOF_PRO_GUITAR_NOTE_FLAG_LINKNEXT`); `src/gp_import.c` sets that flag from the GP slide-type byte only for the "legato" pitched-slide subtype (never "shift"), and separately for tie notes that introduce a new technique not already present on the note they would otherwise fold into, and for grace-note slide-ins (both out of scope here) | `source_import.SourceNoteEvent.link_next`, `guitarpro_import.py:_resolve_slide_target_frets()`, `rocksmith_xml.py` (`linkNext` attribute in `_technique_attributes`), the same reviewed-authority layers as `slide_target_fret` | PARTIAL | port | P1 | Fixed for the legato-pitched-slide case as part of the "Pitched slide" row's correction: a resolved legato slide now exports `linkNext="1"` alongside `slideTo`, a resolved shift slide does not, and an unresolved slide exports neither (never invented without the concrete `slideTo` it describes). Verified with unit tests (`test_guitarpro_import.py`, `test_rocksmith_xml.py`, `test_guitar_rocksmith_xml.py`, `test_reviewed_export_events.py`, `test_reviewed_guitar_authoring.py`, `test_reviewed_rocksmith_xml.py`); not yet packaged-verified. Remains PARTIAL, not PARITY: EOF's tie-note-introduces-a-new-technique case (`gp_import.c` ~4119) and grace-note slide-in case (~4345) are separate `EOF_PRO_GUITAR_NOTE_FLAG_LINKNEXT` sources this project does not yet derive `link_next` from -- see the "Tied notes" row in section A (mixed-technique tie chains are explicitly still unaudited) and the ungraded "grace" technique. |
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
