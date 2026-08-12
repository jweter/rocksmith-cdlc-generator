# Song Preview & Timing Editor

## Purpose

The Song Preview & Timing Editor is the primary human-review workspace for the Rocksmith CDLC Generator desktop application.

The generator's product goal is not one-click arbitrary-song perfection. It is to generate the strongest plausible draft and make correction substantially faster than authoring from scratch. Timing is foundational: a musically correct transcription with a bad beat map is still unusable. Therefore the user must be able to audition, inspect, correct, and approve timing before packaging or testing inside Rocksmith.

This workspace should eventually let the user complete most quality-control work without launching Rocksmith 2014.

## Product position

The application remains Python-based internally, with deterministic/testable CLI and library interfaces underneath a Windows desktop GUI. The CLI is the engine and debugging surface; the GUI is the normal human workflow.

Recommended desktop framework: PySide6 / Qt unless later prototyping demonstrates a materially better Windows option.

The Song Preview & Timing Editor should become the center of the GUI rather than a secondary utility screen.

## Current read-only foundation

The first implementation deliberately stops before editing. `song_preview.py` loads the trusted MusicXML multi-arrangement manifest and projects its normalized Lead/Rhythm/Bass events onto the shared canonical timebase. `build_preview_timeline_window()` then clips beats and arrangement lanes to a requested GUI viewport while preserving each note's full-arrangement event index, confidence, trust class, review state, tuning, string/fret position, and techniques.

The viewport projection is a deep copy: changing GUI-side preview objects cannot mutate the trusted snapshot or imported source artifacts. No timing correction, note correction, packaging action, live Rocksmith write, or NoCableLauncher integration exists in this layer. Editing will be introduced only through separate provenance-aware review artifacts and explicit human actions.

## Core synchronized timeline

The editor should present one shared time axis containing:

- source/normalized audio waveform;
- playback playhead;
- detected beat grid;
- measure/downbeat lines;
- local BPM and time-signature information;
- structural section markers;
- Bass, Lead, and Rhythm note/chord overlays;
- confidence/review state;
- technique markers;
- Rocksmith phrase/handshape/anchor overlays when available;
- tone-change markers when tone analysis is available.

All layers must remain synchronized to the same canonical timebase.

## Playback modes

Required audition modes:

1. Song only.
2. Song + metronome/click.
3. Click only.
4. Isolated stem + click when a stem exists.
5. Song + generated note preview.
6. Bass stem + generated Bass chart.
7. Guitar stem + generated Lead/Rhythm chart.

The click must follow the actual variable-tempo beat map rather than assuming one global BPM.

Song + click is a primary beat-map diagnostic. Timing errors should be audible immediately.

## Transport and navigation

The editor should provide:

- play/pause/stop;
- click-to-seek;
- scrub;
- zoom in/out;
- horizontal timeline navigation;
- jump to next/previous review item;
- jump to next/previous section;
- selection-based looping;
- measure-based looping;
- configurable pre-roll;
- playback-speed reduction for detailed review without changing chart timing.

A user should be able to loop a small region repeatedly while editing it.

## Beat-map visualization

Beat markers should visibly communicate state.

Suggested states:

- high-confidence automatic beat: solid line;
- lower-confidence automatic beat: dashed line;
- suspected timing problem: warning highlight;
- human-approved timing anchor: lock indicator;
- manually edited but not yet approved: distinct edited state.

The exact visual design can change, but provenance and review state must never be hidden.

## Manual timing anchors

Manual anchors are a core requirement.

The user must be able to select a beat/downbeat and establish it as a trusted timing anchor. Anchors should constrain recalculation rather than requiring the user to manually reposition every later beat.

For a selected beat or downbeat, support operations such as:

- nudge -10 ms;
- nudge -1 ms;
- nudge +1 ms;
- nudge +10 ms;
- enter an exact timestamp;
- mark/unmark as hard anchor;
- shift this beat only;
- shift this measure/region;
- refit timing between surrounding trusted anchors;
- recalculate local BPM between anchors.

The exact correction algorithm must be deterministic and testable.

## Piecewise tempo-map editing

Do not force songs onto one BPM.

The editor should support piecewise tempo maps where timing can drift or intentionally change. A correction between two locked anchors should interpolate/refit the beats inside that region without moving approved timing outside the region.

The model should preserve:

- original detector timestamps;
- corrected timestamps;
- detector confidence;
- manual-anchor state;
- revision provenance.

Edits must be reversible and should not destroy the raw analysis artifact.

## Automatic timing diagnostics

The editor should help the user find likely timing problems instead of requiring full-song visual inspection.

Potential diagnostics:

- low beat confidence;
- abrupt unexplained local BPM changes;
- accumulated drift relative to strong transients/downbeats;
- large disagreement between detector engines;
- imported symbolic-source timing disagreement;
- note-onset clusters consistently offset from nearby beats;
- missing/extra beat candidates;
- impossible or suspicious measure durations.

The review queue should surface these regions in priority order.

A typical diagnostic could report:

```text
Measure 31
Timing drift suspected: +73 ms
Beat confidence: 0.61
Review recommended
```

Diagnostics are review hints, not permission to rewrite approved timing silently.

## Note and chart preview

The synchronized timeline should show generated arrangement events for Bass, Lead, and Rhythm.

Selecting an event should expose at least:

- onset timestamp;
- duration;
- MIDI pitch/note name;
- arrangement;
- string;
- fret;
- chord identity where applicable;
- techniques;
- confidence;
- source/provenance;
- review-required state;
- alternate string/fret candidates when available.

The user should be able to correct note timing and physical string/fret placement directly from the review workspace.

## Virtual fretboard

The GUI should include a synchronized virtual fretboard for sanity checking physical mappings.

During playback, current/upcoming notes should be visible on the fretboard. This can reveal implausible position jumps even when pitch transcription is technically correct.

The fretboard should support:

- Bass and six-string guitar layouts;
- current tuning;
- highlighted active notes/chords;
- current hand-position/anchor visualization when available;
- alternate-position preview;
- click/select a candidate position for correction.

## Confidence visualization

Confidence remains a first-class product principle.

The preview/editor should visually distinguish:

- high-confidence generated content;
- moderate-confidence content worth checking;
- low-confidence/review-required content;
- user-confirmed content;
- unresolved content that blocks export/packaging.

No low-confidence event should silently become authoritative because it looks identical to confirmed data in the GUI.

## Structural sections and phrases

The timeline should display detected/confirmed sections such as intro, verse, chorus, bridge, solo, breakdown, and outro.

Users should be able to:

- rename section labels;
- move boundaries;
- add/delete boundaries;
- lock approved boundaries;
- use sections as convenient loop/review ranges.

Later, phrase generation and Dynamic Difficulty review should reuse these timeline structures.

## Tone-change preview

Once tone research and Rocksmith tone mapping are implemented, tone regions should appear on the same timeline.

Example:

```text
0:00  Clean
0:43  Crunch
1:37  Lead Solo
2:05  Crunch
3:12  Clean
```

The user should be able to audition the source around each transition and move/approve the marker.

The editor does not need to perfectly emulate Rocksmith's proprietary DSP before this is useful. Initial tone preview can focus on:

- transition timing;
- researched rig/effect evidence;
- selected Rocksmith components;
- confidence;
- source citations;
- alternate component candidates.

An approximate local DSP preview may be explored later using open-source effects, but it must not block the core editor.

## Review workflow

Suggested review flow:

```text
Generate draft
    ↓
Open Song Workspace
    ↓
Song + click timing review
    ↓
Correct/lock beat anchors
    ↓
Review low-confidence notes/chords
    ↓
Review fretboard mapping
    ↓
Review techniques
    ↓
Review sections/phrases
    ↓
Review tone regions/components
    ↓
Run validation
    ↓
Export/package only when blocking issues are resolved
```

The GUI should make "next thing needing human attention" obvious.

## Data-model requirements

Manual edits must be non-destructive and provenance-aware.

Timing artifacts should distinguish raw analysis from reviewed timing. A future schema may use artifacts similar to:

```text
analysis/beat_map_raw.json
review/timing_edits.json
charts/beat_map_reviewed.json
```

Each reviewed beat should be able to retain:

```text
original_time
reviewed_time
confidence
source_engine
manual_anchor
review_status
revision_reason
```

Equivalent provenance should exist for note, fret, technique, section, and tone edits.

## Validation integration

Packaging must continue to respect PASS/WARNING/FAIL validation.

Examples of timing-related blocking conditions:

- non-monotonic beat timestamps;
- beats outside song bounds;
- impossible local tempo caused by an edit;
- unresolved required timing anchors;
- note events outside the reviewed song timebase;
- timing edits that invalidate aligned symbolic sources without reconciliation.

Warnings can include suspicious but still playable drift or low-confidence automatic regions.

## Performance constraints

Target hardware remains a Windows 11 laptop with approximately 16 GB RAM and no required discrete GPU.

The GUI must remain responsive while heavy stages run. Audio playback/timeline interaction should not require loading transcription or separation models into memory.

Heavy ML stages should remain isolated and sequential. The preview/editor should primarily consume cached artifacts.

## GUI milestone ordering

Do not stop stabilizing the core engine merely to build visual polish. However, the preview/editor should begin earlier than a complete all-features GUI because it directly improves benchmark quality and human correction time.

Recommended order:

1. Stable normalized-audio + beat-map artifacts.
2. Minimal desktop Song Workspace shell.
3. Waveform + playback + variable-tempo click.
4. Beat-grid display and manual anchor editing.
5. Looping and timing diagnostics.
6. Bass note overlay and event correction.
7. Virtual fretboard.
8. Lead/Rhythm overlays.
9. Technique/section/phrase review.
10. Tone-region review and Rocksmith component approval.
11. Validation/build controls.
12. Packaging as a normal Windows executable.

## Acceptance criteria for timing-editor V1

V1 is successful when a user can:

- open a local song project;
- view its waveform and detected beat grid;
- play the song with a click that follows the beat map;
- select and loop a timing region;
- hear/see when the grid is wrong;
- move a downbeat;
- lock trusted anchors;
- refit beats between two anchors;
- preserve the original raw beat map;
- save reviewed timing;
- rerun validation against the reviewed map;
- reopen the project with edits intact.

## Success metric

The preview/editor exists to reduce **human editing minutes per finished song minute** while increasing confidence that timing, notes, fret placement, and tones are correct before Rocksmith packaging.

A feature that looks impressive but does not reduce correction effort or catch errors should not outrank this workflow.
