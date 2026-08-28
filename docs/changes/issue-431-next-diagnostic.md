# Issue #431 — next packaged timing diagnostic

Windows build `d750567a` still reproduces the residual score projection defect after the current v5 leading-rest refinement:

- shared recording Timeline / audible common entrance: ~`7.12 s`;
- Arrangement Preview first Bass/Lead/Rhythm events: ~`11.77 s`;
- residual error: ~`+4.65 s` late.

This change set does not introduce a blind global correction. The correct shared beat/audio clock remains authoritative.

The next packaged build makes the existing EOF reference controls reachable so the human tester can exercise `Open in EOF`, alternate-GP triangulation, and the current EOF recording-clock evidence path directly. A simpler fresh control song should also be tested to separate a Bell-Tolls-specific leading-score structure edge case from a generic score-to-recording transform defect.

Issue #431 remains open until the generic timing cause is fixed and validated against both the representative project and an independent control song.
