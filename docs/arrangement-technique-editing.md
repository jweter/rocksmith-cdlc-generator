# Arrangement Technique Review

This milestone adds explicit human technique correction for one directly selected Bass, Lead, or Rhythm event inside Song Workspace.

## Authority model

Technique edits are stored in `review/reviewed_techniques.json`. Imported score bytes and score fan-out JSON remain immutable.

Every accepted decision is bound to the registered score SHA-256 and format, current fan-out manifest path and SHA-256, arrangement role, confirmed source-track index, stable event index, original source onset/duration, MIDI pitch, and original imported technique set.

Technique authority deliberately does not bind to the promoted shared timing map. Techniques describe the musical event itself, so a later timing re-alignment should not invalidate a valid human technique decision. Changes to score/fan-out/event identity still fail closed.

## Desktop workflow

1. Open **Arrangement Preview**.
2. Select an exact Bass, Lead, or Rhythm event. Overlapping chord tones still require explicit note choice.
3. Review the current comma-separated technique list.
4. Add, remove, or replace supported technique names. An empty list explicitly means no techniques for that event.
5. Click **Accept Techniques**.

Selection and text entry alone grant no musical authority. Only the explicit acceptance action persists the technique set.

Supported technique names are: `accent`, `bend`, `ghost_note`, `grace`, `hammer_on_pull_off`, `harmonic`, `heavy_accent`, `let_ring`, `palm_mute`, `slide`, `staccato`, `tie`, `tremolo_picking`, `trill`, and `vibrato`. Unknown values are rejected rather than passed silently into authoring.

## Preview and draft behavior

The synchronized three-arrangement preview overlays current reviewed techniques after provenance validation.

Lead and Rhythm shared-timeline draft generation applies reviewed techniques to a deep-copied source before chart construction. The source fan-out JSON is never mutated. The draft manifest records the reviewed-technique layer SHA-256, so a later accepted technique edit makes the prior guitar draft stale until regenerated. Existing regeneration cleanup continues to invalidate downstream validation, export, DLC Builder, and staged-package state.

Bass preview uses the same generic technique review layer. The separate Bass authoring/export path does not consume these edits yet; that boundary remains explicit.

## Safety boundaries

Accepting techniques does not accept or change timing, pitch, string/fret position, chord identity/fingering, source rights/provenance, Bass/Lead/Rhythm mapping, overall event trust, validation results, tone choices, or package readiness.

The feature never modifies the live Rocksmith installation or NoCableLauncher and does not introduce commercial/private media into Git.
