# Chord Fingering Acceptance v1

This milestone adds one whole-chord human acceptance action for simultaneous Lead/Rhythm notes in Song Workspace.

## Authority model

Chord fingering does not create a second physical-position authority. `review/reviewed_positions.json` remains the single source of accepted string/fret decisions.

The chord action validates the complete simultaneous source-event group first, then writes every note position to the reviewed-position layer in one atomic update. If any note is invalid, nothing is accepted.

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
2. If it belongs to a simultaneous event group, Song Workspace shows the current chord shape.
3. Resolve any missing or incorrect individual positions using the existing **Accept Position** workflow.
4. Click **Accept Current Chord Fingering**.
5. The entire chord is validated and accepted together.

Selection alone grants no authority. The action does not invent chord membership beyond the current simultaneous source group.

## Safety boundaries

Whole-chord fingering acceptance does not accept or change timing, MIDI pitch, techniques, source rights/provenance, Bass/Lead/Rhythm mapping, tone choices, validation state, or package readiness. Imported score/fan-out artifacts remain immutable. The feature never modifies the live Rocksmith installation or NoCableLauncher.
