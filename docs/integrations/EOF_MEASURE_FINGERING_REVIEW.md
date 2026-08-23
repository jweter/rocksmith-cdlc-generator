# EOF-inspired live fingering review

Last reviewed: 2026-08-22

## Purpose

Make Song Workspace useful for the same fast visual sanity check that makes Editor on Fire (EOF) effective for Rocksmith authoring: play the song while physical string/fret positions move through a synchronized instrument-centric view.

The first measure-inspector slice proved the project can recover authoritative bar and fingering data, but Product Reality showed that a table of MIDI/string/fret values is not the valuable EOF interaction. The valuable interaction is synchronized spatial playback.

## Upstream reference reviewed

Reference implementation: `raynebc/editor-on-fire` (Editor on Fire).

EOF is an established Rocksmith/rhythm-game authoring tool. Its public source/manual were reviewed for behavior and terminology including:

- playback-synchronized 2D note lanes;
- pro-guitar fret/string rendering;
- perspective 3D preview behavior;
- fret-hand-position concepts;
- Rocksmith-oriented lane colors;
- Guitar Pro and Rocksmith authoring workflow.

EOF's own documentation describes selectable color sets including a Rocksmith set, and its pro-guitar code exposes fret-hand-position-aware fingering behavior. Those are useful semantic/reference signals, but this implementation does **not** copy EOF rendering code, source files, or binaries. The project-owned Tk rendering below is an independent implementation over our canonical preview models.

Before any future direct source reuse or redistribution, re-review the exact upstream revision and its BSD-style license/notice requirements. This slice requires no vendored EOF code.

## Product behavior

Arrangement Preview now promotes a **Live fingering preview · EOF / Rocksmith inspired** panel to the primary visual authoring surface.

One arrangement is shown at a time: Bass, Lead, or Rhythm. Arrangement switching preserves the shared song clock.

### Upper pane: 2D string lanes

The upper pane is deliberately close to the useful visual grammar seen in EOF:

- one horizontal lane per physical string;
- tuning/string labels at the left edge;
- fret numbers drawn directly at note onset;
- sustained notes drawn along the string lane for their duration;
- simultaneous notes align vertically and therefore read as chords;
- beat-grid subdivisions are visible;
- musical bar lines and measure numbers are visible when canonical measure timing exists;
- review-required notes receive an additional warning outline, so color is not the only signal;
- technique abbreviations remain visible but secondary;
- a high-contrast playhead moves continuously with normalized project audio.

Click a rendered note to seek directly to it. Clicking empty lane space seeks to that point in the visible window.

### Lower pane: perspective fretboard/highway

The lower pane uses the same authoritative arrangement notes and playback clock, projected into a perspective note highway:

- strings converge toward a horizon;
- the near edge is **NOW**;
- upcoming notes move toward the player as playback advances;
- fret numbers are rendered directly on the note blocks;
- string identity uses a stable Rocksmith-oriented color sequence plus numeric labels;
- review-required notes receive a warning outline;
- the next simultaneous note group is summarized as a physical chord shape when more than one string occurs at the onset;
- clicking a visible highway note seeks to its exact source event time.

The perspective transform is presentation only. It never changes timing, string/fret authority, confidence, or review state.

## Playback synchronization

`PlaybackSongWorkspaceWindow` already polls the local audio transport every 50 ms and updates the shared `_selected_time` playhead. The EOF-inspired mixin repaints both visual panes immediately after that authoritative transport update.

This means waveform, 2D string lanes, perspective fretboard, review navigation, and audio all share one project clock rather than independent approximations.

The live viewport currently keeps approximately 1.5 seconds of recent context and 6 seconds of upcoming material visible. That window is purely visual and can change later without touching musical authority.

## Timing and fingering authority

The view uses existing project-owned `SongPreviewSnapshot`, arrangement notes, tuning, beat grid, and reviewed shared timeline.

Bar boundaries still follow the earlier conservative measure contract:

- GP3/GP4/GP5 measure headers are preferred when preserved as source time-signature events;
- an existing canonical beat grid may derive later measures only when mathematically unambiguous;
- no arbitrary bar duration is invented when source timing is absent.

Displayed string/fret positions are observations from current project authority/review layers. Viewing them does not accept them.

## EOF evidence boundary

EOF remains optional reference evidence. Current source-bound EOF fret-hand-position evidence may be summarized in the live panel, but it does not become canonical state.

Viewing or playing the new visualization does **not**:

- accept a string/fret position;
- change the registered score;
- change Bass/Lead/Rhythm mapping;
- change shared timing;
- change note pitch or techniques;
- create or accept Rocksmith fret-hand-position anchors;
- satisfy validation, XML-export, or packaging gates.

The existing explicit human review controls remain below the live view.

## Product Reality intent

A player should be able to press Play, watch the current arrangement for a few seconds, and answer questions that were difficult in the old table/density presentation:

- Does this chord shape look physically plausible?
- Is the chart suddenly jumping to impossible strings/frets?
- Are note onsets visibly landing in the right musical place?
- Does Lead/Rhythm/Bass look like the part I expect at this moment?
- Is a suspicious event isolated, or part of a repeated systematic error?

This is intentionally closer to how Rocksmith itself communicates notes during play, which should make human validation substantially faster.

## Tests

`tests/test_eof_live_preview.py` covers the pure live-view projection layer:

- bounded look-behind/look-ahead viewport behavior;
- physical string-count resolution from tuning and source positions;
- visible-note clipping;
- perspective highway filtering and geometry inputs;
- instrument fallback behavior.

`tests/test_eof_measure_review.py` continues to cover authoritative bar construction and measure-level fingering summaries.

## Next slices

After Product Reality confirms this live representation is genuinely useful, the next EOF-derived work should focus on:

1. explicit Rocksmith fret-hand-position/anchor overlays;
2. richer chord-name/shape labeling from canonical source data;
3. direct visual note selection wired to existing human-reviewed position/timing/technique actions;
4. phrase/section markers and difficulty context where source authority exists;
5. keyboard/mouse authoring accelerators learned from EOF without weakening provenance or review gates.
