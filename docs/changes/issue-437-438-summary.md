# Deeper EOF parity release slice

This branch combines #437 and #438 so the next Windows build can diagnose the timing path at two distinct boundaries:

1. source structure: registered GP vs private alternate GP;
2. final mapping: EOF-observed recording time vs promoted shared timeline.

The intent is diagnostic depth, not automatic correction. EOF and alternate scores remain advisory evidence while the project retains explicit human review and provenance boundaries.
