# Issue #438 implementation

Implemented on `agent/437-eof-recording-clock-parity` alongside the deeper EOF recording-clock work from #437.

- private alternate GP3/GP4/GP5 comparison;
- Bass/Lead/Rhythm role-by-role structural comparison;
- first-playable source-time delta;
- deterministic coordinate and onset-prefix comparison;
- SHA-bound stale detection for both score files;
- CLI `cdlc-eof --compare-score`;
- Song Workspace **Compare alternate GP…** control;
- advisory status summary in the EOF reference panel;
- no automatic source replacement or authority promotion.
