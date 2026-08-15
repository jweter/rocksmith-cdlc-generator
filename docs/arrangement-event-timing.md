# Arrangement Event Timing Review

This milestone adds explicit human onset/duration correction for one directly selected Bass, Lead, or Rhythm source event inside Song Workspace.

## Authority model

Timing edits are stored in `review/reviewed_event_timing.json`. The imported complete score, arrangement fan-out JSON, and promoted shared timeline remain immutable.

Every accepted decision is bound to:

- registered score SHA-256 and format;
- current score fan-out manifest path and SHA-256;
- current promoted shared-timeline path and SHA-256;
- arrangement role and confirmed source-track index;
- stable source event index;
- original source onset, duration, and MIDI pitch;
- explicitly accepted recording-clock onset and duration.

If the score, mapping/fan-out, source-event identity, or shared timing authority changes, the review layer fails closed instead of silently carrying the old edit forward.

## Desktop workflow

1. Open **Arrangement Preview**.
2. Click an exact Bass, Lead, or Rhythm event. Overlapping chord tones still require an explicit note choice.
3. Review the event detail and synchronized playback position.
4. Change **Start (recording seconds)** and/or **Duration (seconds)**.
5. Click **Accept Event Timing**.

Selection and text entry alone grant no authority. Only the explicit acceptance action persists the edit.

Accepted timing must be non-negative, have positive duration, and end within the project recording duration.

## Preview and draft behavior

The synchronized three-arrangement preview overlays current reviewed event timing on the recording clock.

Lead and Rhythm shared-timeline draft generation applies current reviewed timing to a deep-copied source before chart construction. The source fan-out JSON is never mutated. The resulting draft manifest records the reviewed-event-timing layer SHA-256, so any later accepted timing edit makes the previous guitar draft stale until regenerated. Regeneration continues to invalidate stale validation, export, DLC Builder, and staged-package state.

Bass preview uses the same generic review layer. Bass authoring/export remains on its existing separate path and does not consume these timing edits yet; this limitation is explicit rather than silently implying export authority.

## Safety boundaries

Accepting event timing does **not** accept or change:

- source rights or provenance;
- Bass/Lead/Rhythm score mapping;
- note pitch;
- string/fret position;
- techniques;
- chord identity or fingering;
- overall event trust;
- tone choices;
- validation results;
- package readiness.

The feature never modifies the live Rocksmith installation or NoCableLauncher and does not introduce commercial/private media into Git.
