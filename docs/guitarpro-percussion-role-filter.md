# Guitar Pro percussion role filtering

A Product Reality run exposed a Guitar Pro drum track whose metadata looked bass-like enough to receive a Bass instrument hint. Drum tracks can carry names such as `Bass Drum`, low numeric note/string encodings, or even MIDI-program values that overlap string-instrument heuristics. Those signals are not valid evidence that the track is a playable Bass, Lead, or Rhythm arrangement.

For Guitar Pro inventory, PyGuitarPro's explicit `isPercussionTrack` identity is now authoritative for this narrow classification boundary. Percussion tracks remain present in the full score inventory with their original name, tuning-like metadata, and note count, but they receive no Bass/Guitar instrument hint and are assigned no positive Bass/Lead/Rhythm proposal score.

This is intentionally fail-closed. It does not delete percussion tracks, rewrite the source score, auto-confirm any remaining mapping, or prevent a human from reviewing the complete source inventory. Bass, Lead, and Rhythm proposals remain suggestions requiring explicit human confirmation before fan-out authority is granted.

Safety boundaries are unchanged: no commercial media, private project evidence, CFSM exports, Ubisoft-derived content, generated private project data, live Rocksmith installation state, or NoCableLauncher state is modified or committed.

Related Product Reality finding: #268.
