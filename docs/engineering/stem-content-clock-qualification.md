# Bass separated-audio content-clock qualification — PR #790

## Engineering purpose

Rocksmith's original normalized audio remains the authoritative recording clock.
A separated Bass stem can have exactly matching sample count, rate, channel
layout and source/stem SHA-256 receipts while a separator has delayed its
**musical content** by 40–200 ms. That would make the selected-note audio
review misleading and could corrupt Bass score/audio verification.

This slice introduces a **separate read-only timing diagnosis**, not another
source separator, transcriber, or beat-map adjustment.

## Algorithm

`stem_content_alignment.audit_stem_content_alignment(master, stem)`:

1. Accepts only matching, uncompressed 16-bit mono/stereo WAV geometries.
2. Reads bounded 3-second windows distributed through the song instead of
   importing a full recording into memory. Two cascaded low-pass filters
   (~270 Hz) produce a 10-ms low-frequency log-RMS envelope for each source,
   independently preserving opposite-phase stereo channel energy.
3. Searches offsets in [-250, +250] ms by normalized correlation; **positive
   lag means the stem's content occurs later than the master**.
4. Requires a usable time-varying signal, a strong unique correlation peak
   (>=0.72, >=0.045 clear margin) in at least two independently located
   windows, and agreement among the accepted lag estimates (25 ms tolerance).
5. Emits one of `aligned`, `shifted`, `ambiguous`,
   `insufficient_signal`, `incompatible` plus measured lag, per-window
   estimates and explanation. Only `aligned` may support the existing
   Bass reconciliation trust-promotion gate; any other outcome retains
   `symbolic_unverified`/review-required status.

`reconcile-bass` also writes
`analysis/bass_stem_content_alignment.json`, bound to the current recording
and stem hashes. It contains only timing measurements, status and hashes,
not music bytes, paths, artist/song names, or score notes. It is generated
locally each time, not trusted as a previously cached PASS.

## What this measures — and what it does not

This audit measures **content latency between the actual two files**. It
cannot prove the Bass stem has only Bass, that the detected note has correct
pitch, or that Lead/Rhythm are separated. Even the *identical full mix*
passes the content-clock test, so instrument identity must be a separate
qualification step. Master-versus-stem content may be too different for
correlation: an ambiguous result is not a defect to work around by
lowering thresholds, and it must never be promoted to PASS.

A 10-ms envelope intentionally does not establish millisecond-level
playback latency or phase fidelity. Windowed normalized correlation is
susceptible to periodic riffs or strong low-frequency drums. Bounded,
unique-peak and multi-window conditions reduce false confidence but do not
establish correctness on arbitrary production mixes.

The historic ~two-measure score-to-recording misalignment remains a distinct
problem owned by the shared score/recording timing gate (#455/#612). This
stem audit **must not** shift source notes, beat grids or audio automatically.

## Automated acceptance

Synthetic Bass + drum signals with known injected 0, +40, +200 and -80 ms
stem delay must report `aligned` for 0 and `shifted` at the correct
sign/magnitude for each nonzero case. Silent, unrelated, malformed and
short inputs must not be qualified. Integration tests mutate a stem and
rewrite a perfectly valid receipt: the reconciliation trust gate must still
reject its 40/200 ms shift. The suite additionally reuses the existing
`auto_cdlc_truth` original-sample-clock fixture (#775) to ensure a
reproducible legal reference, without creating a parallel benchmark system.

Persisted reconciled Bass charts prior to algorithm version 4 are stale and
must be regenerated under this stronger timing gate.

## Next work

Evaluate this conservative detector against privately held, lawfully
available separated Bass stems and varied mixes to measure false PASS,
false ambiguity, latency error, CPU/RAM, intro/outro silence and repeated
riff failure rates. If cross-correlated envelopes fail too often, compare
onset landmarks and multiband chroma/harmonics before raising confidence.
Only separately validated stem content, stem identity, and note evidence
may qualify a chart. No user-directed repetitive laptop test is needed
for the automated synthetic validation.
