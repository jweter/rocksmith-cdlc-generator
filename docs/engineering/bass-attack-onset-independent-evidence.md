# Per-event independent Bass attack/onset evidence — issue #796 slice 32

**Scope:** a conservative, local 16-bit PCM source check in the production Bass
note qualification path. It neither transcribes pitches nor grants independent
music, time alignment, source separation, commercial-audio rights or gameplay
authority. The historical approximately two-bar arrangement delay is **not**
solved by this work.

## Reproduced logical weakness

The established pYIN transcriber generates `pitch_confidence` from its
fundamental-frequency estimate and `timing_confidence` from a Librosa onset
envelope. The latter uses the **detected peak**, not the backtracked minimum
(PR #734), but it is still stored in the same model-supplied `NoteEvent`.
A candidate note can claim a high overall, pitch *and* timing confidence even
when the underlying local stem carries no fresh attack at the claimed event
time. Independent onset evidence must come from the current, verified stem
PCM itself, not the classifier's own metadata.

## Implementation and acceptance

`bass_attack_evidence.inspect_bass_attack_onset()` reads exactly one bounded
270-ms region around each candidate event: 120 ms before and 150 ms after its
predicted onset. 10-ms DC-corrected per-channel RMS segments prevent audio
phase cancellation in polarity-inverted stereo. For each plausible attack
between the proposed onset and **80 ms later** (accommodating Librosa's
legitimate boundary backtracking), compare the mean 30-ms post-onset RMS with
the preceding 30-ms mean. Independent attack acceptance requires:

- at least **250 PCM RMS** in **each** of three post-attack 10-ms segments,
  avoiding a single loud click;
- a minimum **200 PCM RMS** post/pre jump;
- a minimum post/pre ratio of **2.5**, yielding a conservative
  confidence `1 − 1 / ratio >= 0.60`;
- the candidate attack observed no more than 80 ms after the backtracked
  event boundary.

Returns `attack_detected`, `no_attack`, `insufficient_signal`, or
`unavailable`, with sanitized numeric evidence (confidence, pre/post RMS,
onset delta) and constant false musical-authority booleans.

`reconcile_project_bass` supplies the probe only after verifying the
hash-bound current Bass stem, recording/content clock and existing source
negative controls. `reconcile_bass_sources` executes it only for
otherwise-QUALIFIED, score-matched events, *after* octave-leakage checks.
The outcomes `NO_INDEPENDENT_ATTACK`,
`INSUFFICIENT_ATTACK_EVIDENCE`, `ATTACK_SCREEN_UNAVAILABLE`, and
`LOW_INDEPENDENT_ATTACK_CONFIDENCE` prevent `symbolic_verified`.
Already-unqualified notes do not launch extra analysis. Observations and
the two exact thresholds are stored per note for review.

The reconciliation algorithm advances **v8 → v9**; cached v8 or older charts
must regenerate and cannot inherit newly required onset authority.

## Synthetic test coverage (no user laptop)

Original 8-kHz synthesized E1 audio has attacks exactly at the predicted note
and 40 ms later; both can be detected independently of MIDI/f0. Other fixtures
cover silence, DC-only PCM, a steady tone with convincing f0 but no attack,
an onset 110 ms late, an isolated 3-ms impulse, stereo inverse polarity,
invalid timing, missing or truncated WAV, an extremely short note or absent
pre-roll, and all earlier score/provenance gates deliberately simulated as
successful with **100% confidence**. Verify that apparent pitch without attack
remains review-only rather than promoting symbolic authority. Also test
unavailable and unknown probes fail closed, all prior v8 charts become stale,
and the sanitized evidence contains no private filename.

## Limits and next measurement

This is **necessary onset contrast, not Bass identity**: other instruments,
drums or a synthesized sound can produce a valid RMS attack. The existing
source-provenance and Bass silence/percussion/octave checks remain mandatory.
Conversely, a legato or softly articulated real Bass note, very low amplitude,
note at the start of the recording, or transient more than 80 ms late may
remain review-required. Thresholds are deterministic synthetic **engineering
guards**, not experimentally calibrated false-positive/false-negative rates
on lawful real songs. Real-song agreement, independent note truth, Lead/Rhythm,
the original two-measure timing issue and actual Rocksmith gameplay remain
unproven.
