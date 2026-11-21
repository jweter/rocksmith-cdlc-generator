# Tuning-aware Instrument Audio Evidence in Arrangement Preview

Status: **implementation contract**, not shipped functionality.
Tracking: [#787](https://github.com/jweter/rocksmith-cdlc-generator/issues/787).
Related: #612 (private unattended acceptance), #455 (shared beat authority), #563 (small-window layout), `docs/integrations/AUDIO_EVIDENCE_PIPELINE.md`.

## User intent

As a musician reviewing Bass, Lead or Rhythm notes, I want the relevant instrument's frequency energy and isolated audio (when available) directly beside the selected event and tab, so I can **see, hear and compare** possible pitches, string/fret assignments and onsets without leaving Arrangement Preview.

This is not a stand-alone equalizer or an alternative song clock. The panel is supporting **audio evidence** and a faster review surface; the canonical score and independently qualified shared recording/beat mapping remain authoritative unless explicitly edited through existing gates.

## Where to integrate

The existing `LiveReviewEnhancementMixin` in `src/rocksmith_cdlc_generator/live_review_enhancements.py` already provides a selected-note/chord inspector, first/next-note seek, human marks, and transport controls. Put an optional, compact/collapsible **Instrument Audio Evidence** section immediately beneath the selected-note inspector, above the tab and highway view.

The panel follows the existing `_live_selected_event` and `_active_measure_arrangement()`. It must not duplicate the underlying note model or independently advance song time. All transports and spectral/waveform timestamps use the same `ProjectAudioTransport.position_seconds` and same promoted score->recording mapping. A changed role or project invalidates the previous preview/stem selection.

## Review experience

1. Choose **Bass / Lead / Rhythm** through the existing arrangement selector, not a second conflicting role control.
2. Click a note/chord or seek a review-required item. Show event index, recording time, pitch candidates, tuning, string/fret, duration, source and trust/confidence.
3. Toggle **Original mix** / **Frequency-focused** / **Separated stem** (if available). The last two modes must be conspicuously distinguished. A filter is not isolation; `guitar` stem is not by itself `lead` vs `rhythm` isolation.
4. Audition the selected event in a small adjustable A/B loop, preserving song time when switching modes; preserve independent click/reference control.
5. Show aligned source waveform(s) and a log-frequency spectrum/CQT or spectrogram window with candidate fundamentals, harmonics, onset markers and disagreement highlights. Show the actual measured data, never a fabricated spectrum.
6. If a verified tuning is present, show physically plausible fret/string choices for candidate MIDI pitches. A candidate does not become a score edit until the existing explicit reviewed-edit-and-validation workflow accepts it.
7. Display `audio_supports_score`, `audio_disagrees`, `audio_ambiguous`, `insufficient_signal` or `analysis_unavailable`, alongside source/model/parameters. Missing stems or failed analysis should fall back to original mix without blocking review.
8. The panel must remain usable at small laptop window sizes, with visible scroll support and no always-open large empty canvas.

## Technical contract

### Tuning-aware audio focus

- Consume **confirmed** `PreviewArrangement.tuning_midi`, not guessed note names. Validate 4/5/6-string Bass, six- or other supported string-count guitar, alternative tuning and physical fret limits as configured.
- Convert MIDI to equal-tempered fundamental frequency: `f(m) = 440 * 2**((m-69)/12)`. Derive low-register focus and candidate note/harmonic guides from actual tuning and the selected event, without a single hard-coded 230/430 Hz filter for every instrument.
- Retain the lowest tuned open-string fundamental and enough harmonics for pitch evidence. Do not pretend that low-pass or band-pass suppresses overlapping kick drums, keyboards, rhythm guitar, vocals or upper harmonics perfectly.
- `frequency-focused`: reversible, deterministic DSP listening/visualization product. Offline render and cache in the project's private derived-audio directory, keyed by source SHA-256, sample rate, tuning, selected profile, DSP version and processing parameters. Render with appropriate channel behavior/headroom and explicit phase/latency handling. Prefer chunked/bounded computation and never block Tk's event loop.
- `separated stem`: reuse the optional `stems.py`/`audio-separator` boundary. No new mandatory model or cloud upload; model evidence includes provider, model and hash. A missing, corrupt or misaligned stem is unavailable, not grounds for inference.
- Transcription is a **third** process: use credible, independently qualified stem note evidence, not just more pYIN detections from a filtered full mix. The prior private 12-second experiment gave more candidates after filtering, but zero sufficiently strong notes.

### Timing and authority

- The original normalized recording and its beat grid are the timing authority. All preview sources must resolve to the same recording-relative frame positions and agreed sample rate / duration, or refuse playback with a comprehensible reason.
- Switching preview modes cannot change score timestamps, shared alignment, accepted note events, or playback cursor location. Compensate or report filter/separator delay explicitly; never hide a two-measure offset by rephasing the chart.
- Cache derived spectra/note evidence against the **source and processing provenance**; invalidate on changed source, selected role, verified tuning, algorithm version or model parameters.
- Previewing/hearing a note must never auto-accept edits, mark review items complete, or bypass low-confidence/rights/timing gates.
- No private/commercial audio, stems or source scores are committed, pushed in PR comments, or embedded in public browser reports.

## Suggested API seams

- `InstrumentAudioFocusProfile`: role, verified tuning MIDI, playable pitch range, selected fundamental/harmonics, DSP profile/parameters, version; absent/invalid tuning => focus unavailable or explicit limited generic audition, **never guessed tuning**.
- `InstrumentAudioEvidence`: event ID, recording-time window, source type (`original`/`focused`/`stem`), source/hash/model, measured spectral/onset/pitch candidates, reliability status, warnings.
- `prepare_focus_preview(project, role, tuning, parameters)`: cacheable, bounded-background render; preserve original file. No automatic authoring mutation.
- `set_preview_source(source)` on the **existing** audio transport or an equivalent shared-clock source selector; validate PCM properties, same duration and frame/clock mapping before switching. Do not instantiate independent playing clocks for each source.
- `select_note` and `_refresh_eof_live_preview` are the existing integration points; heavy DSP runs off-thread and the Tk callback only updates the display.

## Delivery slices and mandatory tests

**Slice A — deterministic audio focus backend**
- Validate tuning/register/pitch-to-frequency/harmonic and fret candidate calculations; handle Bass B0/low E and drop-tuned guitars.
- Produce private PCM-focused audio with measured frame count and cache/invalidation metadata.
- Synthetic tests with isolated E1, E2, kick-like transient and overlapping instruments. Verify filter makes suitable energy more audible but cannot infer that it isolated a specific instrument.

**Slice B — integrated selected-note audition**
- Add compact review-side audio panel with Original/Focused/Stem choices.
- Use the same Song Workspace playback clock and selected event; active/inactive source switching must retain position and loop.
- Verify absence/staleness, unsupported formats, user scrolling, high-DPI/short windows and real-time transport remains functional.

**Slice C — visual spectrum and evidence-driven candidate review**
- Plot actual waveform / spectrogram/CQT plus note-onset, harmonic and candidate string/fret markers.
- Distinguish monophonic Bass from polyphonic/distorted Lead/Rhythm and competing sources; ambiguous evidence remains flagged.
- Integrate with existing explicit review/edit gate, without automatic authority promotion.

**Slice D — autonomous acceptance/benchmark**
- Use synthetic/legal multitrack fixtures and private unattended runner from #612 for timing/latency, onset/pitch precision/recall, octave errors, false positives, RAM and CPU duration.
- Acceptance must be backed by independent scored fixtures and evidence linked to the exact generator commit and audio hash; do not request recurring manual owner retests.

## Definition of done

Selecting a Bass/Lead/Rhythm note in Arrangement Preview lets the reviewer **see actual source spectrum and hear original versus instrument-focused versus available separated audio in sync**, see tuning-constrained candidate note positions, and explicitly resolve uncertain notes with no silent time shifts or false confidence.

This document records the design; **the feature is not finished merely because this contract or #787 exists**.
