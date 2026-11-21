# Resource-admitted Bass audio A/B benchmark (issue #787)

## Objective and bounded deliverable

Compare **original mix**, **frequency-focused preview**, and an *already prepared*
hash-bound local **Bass stem** against *the same authoritative notes and original
recording clock*. Score each with our **existing** `BenchmarkChart`,
`from_bass_transcription` and `evaluate_chart`, rather than counting raw
candidate events or inventing another truth standard.

This slice deliberately **does not download, install or run a separation model**.
It is the offline evaluation lane to use **after** an owner-licensed,
resource-approved separator has produced a Bass stem locally. A filename that
says `bass.wav` is not proof of Bass isolation. All comparison verdicts are
`READINESS_ONLY`, `COMPARISON_SCORED`, or `BLOCKED_OR_UNQUALIFIED`,
**never** musical PASS, separator-purity PASS, Rocksmith gameplay PASS.

## Standard workflow (synthetic and private)

First generate the existing copyright-free original WAV with verified first
note at 7.130s and an independent 36-note reference:

```powershell
cdlc-auto-cdlc-truth generate --out-dir C:\RocksmithLocal\test-truth
```

Place an identical copy of `original_synthetic.wav` at
`C:\RocksmithLocal\song-project\audio\normalized.wav`. This is an isolated
test project, not a commercial audio or game directory. Optional prepared
artifacts in this **same** project:

- Focused WAV under `audio/derived/instrument_focus/` with its matching
  SHA-256/render parameters receipt. See `prepare_focused_audio`; no
  artifact is created implicitly by the comparison command.
- Bass stem at `stems/bass.wav` and its current `stems/bass.json`
  receipt from our existing separator adapter. The content-clock audit
  from PR #790 must be inspected: `STEM_CLOCK_SHIFTED` and other
  ambiguous statuses are **unqualified evidence**, regardless of note F1.

Run readiness mode first. No librosa import, transcriber or separator runs:

```powershell
cdlc-bass-evidence-compare --fixture-dir C:\RocksmithLocal\test-truth `
  --project-dir C:\RocksmithLocal\song-project `
  --out C:\RocksmithLocal\song-project\analysis\bass-source-comparison.json
```

For explicitly authorized *local CPU transcription* on the short synthetic
fixture only, add `--execute` and, where prepared, `--focused-wav
C:\RocksmithLocal\song-project\audio\derived\instrument_focus\<hash>.wav`.
The command checks **available physical RAM >=4 GiB**, free disk >=2 GiB,
one original fixture <=45 seconds / 30 MiB and matching WAV geometry.
Every analysis uses the original file's sample clock and checks the exact
input digest **again** against the transcriber output. It does not
change existing `analysis/bass_raw.json`, score, UI note track or PSARC.

## Evidence and limitations

Each source row reports current source digest, readiness, raw note F1,
qualified-note F1, onset MAE, false positives and review burden; qualified
notes must independently satisfy the current overall/pitch/timing confidence
requirements. An old or unbound pYIN transcription cannot masquerade as
verified source analysis. Note-count inflation without qualified F1
improvement is recorded, not celebrated.

The report is JSON with **aggregate metrics and input hashes only**; no
commercial audio, note event lists, local file paths, artist/song metadata,
secrets, or model logs. It is local to the project.

The first implementation measures **wall-clock runtime** and available
physical RAM *before* execution; it intentionally records
`peak_process_ram_gib: null` because no fit-for-purpose process peak
memory profiler has been verified. Do not interpret that null as low
memory usage. The 4-GiB threshold is a conservative admission for
the existing pYIN process, **not a safe authorization for an external
source separator**. Model weights, provenance, license, CPU/GPU peak
memory, Windows low-priority subprocess execution, private song behavior,
Bass/Lead/Rhythm parity and real Rocksmith correctness remain separate
required validation.

The synthetic test uses fake transcription evidence when evaluating
orchestration. The committed tests must never be reported as an actual
run of pYIN or of a Bass separation model. When actual local evidence
is available, run the same tool with an *approved* validated stem; only
after independent scoring should a provider be considered for default use.

No repeated manual laptop tests are needed for these deterministic
regression tests.
