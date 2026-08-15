# Reviewed Chord Identity v1

This milestone adds explicit human authority over which nearby Lead/Rhythm source events belong to one chord when automatic simultaneity grouping is wrong.

## Authority model

Chord identity is stored separately in `review/reviewed_chords.json`. Imported score/fan-out bytes, MIDI pitch, event timing, string/fret positions, and techniques remain unchanged.

Each accepted chord decision is bound to the current score SHA/format, score fan-out SHA, arrangement role, confirmed source-track index, stable source event indices, source onsets, and source MIDI pitches. A stale score, fan-out, source track, onset, or pitch causes the review layer to fail closed.

One source event may belong to at most one reviewed chord. Accepting a new group replaces any current reviewed group that overlaps the selected events.

## Safety limits

A reviewed chord requires at least two events from one Lead or Rhythm source track. The selected source events must fall within 125 ms of each other. This permits explicit correction of small notation/onset disagreements without allowing unrelated distant notes to be grouped into a Rocksmith chord.

Chord identity acceptance does not accept timing, pitch, fingering, techniques, source rights/provenance, mapping, validation, tones, or package readiness.

## Desktop workflow

1. Select one Lead or Rhythm event in Arrangement Preview.
2. Song Workspace prefills the current reviewed group when one exists; otherwise it suggests the automatic source-onset chord candidate.
3. Edit the comma-separated source event indices if the automatic grouping is wrong.
4. The selected event must remain part of the proposed group.
5. Click **Accept Chord Identity**.

Text entry alone grants no authority. Only the explicit acceptance action persists the chord group.

## Draft behavior

Lead/Rhythm shared-timeline authoring consumes current reviewed chord groups by stable source event index. Explicit reviewed groups override automatic onset grouping for those events only; all other events continue through the existing deterministic grouping path.

If any reviewed chord member lacks a valid physical position, none of the remaining members are exported as standalone notes. The group remains unresolved rather than silently degrading into a partial chord.

Shared guitar draft manifests record the reviewed-chord layer SHA. A later accepted chord-identity change therefore makes the prior draft stale until regenerated, preserving downstream validation/export/package invalidation behavior.

The feature never modifies the live Rocksmith installation or NoCableLauncher and does not introduce commercial/private media or generated private project data into Git.
