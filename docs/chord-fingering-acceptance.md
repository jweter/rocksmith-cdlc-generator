# Chord Fingering Acceptance v1

This milestone adds one whole-chord human acceptance action for simultaneous Lead/Rhythm source notes in Song Workspace.

## Authority model

Chord fingering does not create a second physical-position authority. `review/reviewed_positions.json` remains the single source of accepted string/fret decisions.

Chord membership is derived from the immutable source-note onsets in the current score fan-out, using the same source-clock grouping tolerance that final acceptance validates. Recording-clock preview timing may contain per-event reviewed timing overrides, but those overrides do not redefine which source events constitute a chord.

The chord editor collects every tone's proposed string/fret position in temporary UI fields. None of those drafts grants authority. The chord action validates the complete simultaneous source-event group first, then writes every note position to the reviewed-position layer in one atomic update. If any note is invalid, nothing from that chord draft is accepted.

Validation requires:

- at least two source events;
- one Lead or Rhythm source track;
- source onsets within the chord grouping tolerance;
- explicit source tuning;
- one unique physical string per note;
- every string/fret pair to reproduce that event's source MIDI pitch.

Because Lead/Rhythm draft manifests already bind to the reviewed-position SHA, accepting or changing a chord fingering makes older drafts stale without adding another provenance mechanism.

## Desktop workflow

1. Select a Lead or Rhythm note in Arrangement Preview.
2. If the selected event belongs to a simultaneous source-event group, Song Workspace shows one temporary string/fret row for every chord tone.
3. Enter or correct every proposed position inside the chord panel. Existing reviewed/source positions are prefilled when available, but editing these fields alone writes nothing.
4. Click **Accept Current Chord Fingering**.
5. The entire chord is pitch/tuning/string/source-onset validated and then accepted in one reviewed-position write.

Selection and field editing alone grant no authority. The action does not invent chord membership from recording-clock coincidence and does not require individually accepting positions first.

## Safety boundaries

Whole-chord fingering acceptance does not accept or change timing, MIDI pitch, techniques, source rights/provenance, Bass/Lead/Rhythm mapping, tone choices, validation state, or package readiness. Imported score/fan-out artifacts remain immutable. The feature never modifies the live Rocksmith installation or NoCableLauncher.
