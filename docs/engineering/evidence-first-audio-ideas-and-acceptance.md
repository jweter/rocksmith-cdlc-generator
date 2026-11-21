# Evidence-first Rocksmith audio roadmap — achievable follow-up slices

Status: ranked proposals and small-slice acceptance contracts, not claims that all features are implemented.
Parent work: #787 (instrument review), #612 (unattended private Product Reality), #455 (shared timing), source reconciliation ADR-014.
Baseline: PR #788 provides tuning-aware **audition EQ**, local stem switching, a 36-bin log-frequency spectrum and shared transport. An EQ is **not** source separation; a spectrum indicator is **not** evidence of note identity.

## What current behavior proves and does not prove

- The low-pass pilot generated 20/33/29 raw note candidates from one 12-second clip (original / 230 Hz / 430 Hz) but zero qualified notes in all variants. Increased count did not improve verified precision.
- A 0.18-second spectral window has nominal Fourier bin spacing ~5.56 Hz. The equal-tempered E1↔F1 interval is ~2.45 Hz, so one short displayed spectrum **cannot** establish a correct semitone at low Bass E. Use longer, stationary windows or informative higher harmonics and cross-frame evidence, while controlling for adjacent notes and octaves.
- A frame-count/sample-rate-matched stem can still have **internal DSP delay** or source leakage. Validate alignment from actual musical content, not metadata alone; reject ambiguous estimates.
- Knowing tuning constrains playable pitches, not which instrument produced the sound, nor which string played a pitch when multiple positions are possible.
- Guitar Lead/Rhythm is a role distinction that a generic `guitar` separator does not resolve. Stereo/panning may help sometimes, but only when the original recording actually separates the parts.

## Prioritized experiments and defined exits

| Priority | Slice | Small achievable starting point | Falsifiable exit | Caveats |
|---|---|---|---|---|
| P0 | **Bass trust gate v3** | Gate `symbolic_verified` on independently strong pitch/onset confidence and hash-bound Bass stem provenance | Synthetic high-confidence full mix can **never** promote; verified stem + correct note can; old v2 chart is stale | This protects bad evidence; it does not create good evidence |
| P0 | **Expand existing known-truth corpus** | Reuse `cdlc-auto-cdlc-truth` (#775), `BenchmarkChart` and `scripts/run_benchmark.py`; add legal 4/5-string Bass, guitar, drum/noise and source-delay cases | Existing evaluator reports per-note precision/recall, octave error, onset error, drift and false PASS against exact build | Do **not** build a parallel evaluator or rely only on synthetic tones |
| P0 | **Stem clock alignment audit** | Detect bounded time shift with band-limited onset envelopes/cross correlation + independent landmarks; retain unknown result | Synthetic 0/40/200 ms shifts detected, silent/repetitive cases refuse a confident answer | Bass-only vs full mix onset content may be weak; never shift score timing to match a stem |
| P1 | **Resource-gated local stem pilot** | Compare one proven local Bass separator on 12-second snippets against current EQ/full mix and record RAM, elapsed time, stem hashes | Increased *qualified* pitch/onset F1 and zero new false authoring PASS; model fits Azathoth's real available memory | No unconditional whole-song model work during hourly worker |
| P1 | **Harmonic-comb note evidence** | Score candidate F0 and 2×/3×/4× harmonics over multiple stationary windows; test octave errors, note transitions and kick transients | Synthetic E1/F1 and octave-confusion negatives do not pass falsely; result includes insufficient-signal status | Harmonic dominance varies with tone/distortion; chord polyphony requires separate analysis |
| P1 | **Review heatmap and audio A/B** | Surface discrepancy rate by beat/bar; jump to highest-impact uncertainties instead of thousands of note clicks | Identical event selection, original/focused/stem timing and review state; reduces manual events for fixed ground-truth case | Human approval still explicit for unresolved cases |
| P2 | **Stereo/HPSS guitar experiments** | Compare left/right/mid-side and harmonic/percussive separated signals with verified score roles | Improvement in validated Lead/Rhythm note precision vs full mix on held-out samples | Pan is not instrument identity; HPSS is not Lead/Rhythm isolation |
| P2 | **Polyphonic guitar candidate extraction** | Evaluate local Basic Pitch on a proven guitar stem with tuning-aware note range, overlapping-chord tests and bends | Measurable polyphonic note precision/recall, bend timing and no false chord-confidence promotion | Instrument agnostic ≠ role aware; source leakage and distorted overtones can create phantom notes |
| P2 | **Fret-path optimization** | Use candidate positions over entire phrase and prefer minimal hand jumps/string changes while retaining known score positions | On licensed/hand-authored fixtures, recommended string/fret paths minimize deterministic ergonomic cost | A score's explicit physical fingering has priority |
| P2 | **Truth-aware model routing** | Run cheap deterministic checks first, invoke bigger local models only on unresolved, resource-safe sections | Reduces peak RAM/runtime while maintaining or improving qualified accuracy | Must preserve policy and evidence provenance |

## Decision rules

1. **One recording clock:** never use symbolic event time, audio-stem playback time or a model's detected onset as a replacement for the original audio beat map without an independently qualified transformation.
2. **Reconcile, do not overwrite:** each model yields evidence records with source/hash/provider/parameter/window; authoritative arrangement state changes only via existing reviewed-edit gates.
3. **No confidence alchemy:** more detector events, cleaner audio, a stronger-looking plot, or cross-model agreement on the same leaked signal do not constitute a verified note.
4. **Bounded cheap-first architecture:** deterministic DSP and source hashes can run broadly; resource-heavy separation must be chunked/limited and explicitly admitted by the local worker's available RAM.
5. **Unattended truth tests:** CI runs legal synthetic/hand-scored musical fixtures, private local worker runs user-owned song checks; only unautomatable gameplay feel or subjective musical decisions reach the owner.
6. **Benchmark before promoting:** measure false positives and false “PASS” along with precision, recall, onset error, octave confusions, latency, peak RAM and operator review burden. Source rights remain local.

## Preferred next three vertical slices

A. Land **v3 trust gate** and missing-evidence diagnostics (small and immediately risk reducing).
B. Extend the **existing** known-truth generator/benchmark with actual stem delay and signal ambiguity cases; implement stem alignment qualification, not another scoring framework.
C. Pilot **isolated Bass transcription** with the same strict gates; only then try guitar-specific polyphonic/role experiments.

Reuse the repository's existing benchmark ladder and the synthetic original-clock sentinel under #772. The current 7.130-second first-onset synthetic case is an excellent timing negative but not itself evidence that real instrument separation or full-song transcription works.\n\nThese are prioritized ideas, not execution authorizations beyond the already approved Rocksmith project scope. No unattended worker schedule, other repositories, merge protections or device application should change here.
