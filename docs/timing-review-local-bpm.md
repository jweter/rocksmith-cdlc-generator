# Timing review local BPM

A Product Reality run showed that tempo/BPM was not visible while reviewing beat timing. The final Song Workspace now appends the local beat-to-beat tempo to the selected-beat description.

The displayed value is derived from the timing grid currently being reviewed. If human-reviewed beat timestamps exist, those reviewed timestamps are used; otherwise the detected beat grid is used. For a selected beat, the interval to the following beat is preferred so the value describes the tempo immediately ahead of the cursor. The final beat falls back to the preceding interval.

This is a read-only diagnostic. It does not alter beat timestamps, infer or write a tempo map, lock anchors, accept timing, promote the shared timeline, change arrangement notes, or affect packaging. Invalid, duplicate, or insufficient beat times produce no BPM value rather than inventing one.

Safety boundaries are unchanged: uncertain timing remains human-controlled, source and arrangement review gates remain authoritative, and the feature does not touch the live Rocksmith installation or NoCableLauncher or add commercial/private media, CFSM exports, generated private project data, or Ubisoft-derived content.
