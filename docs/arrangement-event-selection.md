# Arrangement Event Selection v1

## Purpose

Song Workspace can now select any visible Bass, Lead, or Rhythm score event directly from its synchronized arrangement lane. This removes the previous restriction that the position editor could only be reached through the review-required queue.

## Behavior

- Clicking a note/chord event selects that exact arrangement event and moves the playhead to its recording-time onset.
- Selection is lane-scoped, so overlapping Bass/Lead/Rhythm events cannot be confused across arrangements.
- A small zoom-relative hit tolerance makes very short events clickable without changing their timing.
- The selected event is highlighted and its source identity, confidence, trust class, techniques, physical position, and review-required state are shown.
- The existing provenance-aware **Accept Position** action is reused for directly selected events.
- Clicking empty lane space only seeks the playhead and does not create or accept an edit.

## Authority and safety

Direct selection is navigation only. It does not grant musical authority and does not modify imported score/fan-out data.

Selecting an event does **not** confirm:

- source rights or provenance;
- Bass/Lead/Rhythm track mapping;
- note pitch, onset, duration, or techniques;
- string/fret placement;
- timing promotion;
- validation state;
- tones;
- package readiness.

Physical position remains an explicit separate human decision through the reviewed-position layer. Pitch/tuning validation and stale-provenance checks from that layer remain unchanged.

## Scope boundary

This slice intentionally does not add note timing, duration, technique, or chord mutation. It establishes deterministic arbitrary-event selection first so those later editors can share one stable event-selection model rather than each inventing its own navigation logic.
