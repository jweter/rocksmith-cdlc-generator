# Benchmark Corpus

This directory defines the evaluation contract for musical-authoring quality. Do not commit commercial recordings, commercial tablature, or copyrighted Rocksmith packages here. Keep private/local benchmark media outside Git and commit only synthetic/public-domain fixtures or metadata that is legally redistributable.

## Purpose

The benchmark exists to answer one product question: **does the generator produce a draft that is substantially faster to correct than authoring from scratch?**

Each case should have a trusted reference chart and a generated prediction represented as `BenchmarkChart` JSON. The evaluator scores note identity/timing separately from fretboard placement and technique inference so improvements can be attributed to the correct stage.

## Recommended initial corpus

Build 5–10 short cases before optimizing models. Cover at least:

- simple monophonic bass
- repeated bass notes with tight onsets
- melodic bass with position choices
- alternate/drop tuning
- sparse lead guitar
- lead with slides/bends/hammer-ons/pull-offs
- rhythm power chords/dyads
- fuller rhythm chords
- one intentionally difficult/noisy mix

Prefer 30–90 second excerpts. A small trusted corpus is more useful than a large uncertain one.

## Core metrics

- exact-pitch note precision, recall, and F1 within a configurable onset tolerance
- onset mean absolute error
- duration mean absolute error
- physical string/fret accuracy on comparable matched notes
- technique precision, recall, and F1
- review-required burden
- unresolved-position burden
- human editing seconds
- editing minutes per finished minute

`editing minutes per finished minute` is the principal end-user productivity metric. For example, 90 seconds of correction on a 60-second excerpt scores 1.5 edit minutes per finished minute.

## Running a suite

Create reference and prediction `BenchmarkChart` JSON files, then run:

```powershell
python scripts/run_benchmark.py `
  --reference benchmarks/local/case1.reference.json `
  --predicted benchmarks/local/case1.predicted.json `
  --reference benchmarks/local/case2.reference.json `
  --predicted benchmarks/local/case2.predicted.json `
  --output benchmarks/local/report.json
```

A JSON report and Markdown sibling are written. The default exact-note onset tolerance is 120 ms; override it with `--onset-tolerance` when a benchmark protocol requires a different threshold.

## Creating benchmark charts from generator artifacts

Use `rocksmith_cdlc_generator.benchmark_adapters`:

- `from_bass_transcription(...)`
- `from_bass_mapping(...)`
- `from_guitar_authoring(...)`

Reference charts should come from a source you have deliberately accepted as ground truth. Do not silently treat an imported tab or an existing CDLC as truth merely because it is structured.

## Evaluation rules

1. Exact note matching requires identical MIDI pitch plus onset within tolerance.
2. Matching is one-to-one and chooses the smallest onset error first.
3. String/fret accuracy is scored only after musical note matching and only when both sides have physical positions.
4. Unresolved positioned notes may still match musical pitch/onset; they remain separately visible through the unresolved metric.
5. Techniques are compared as sets on matched notes.
6. Record human editing time only from an actual correction session. Do not estimate it after the fact.
7. Keep model/tool/config versions with the generator run that produced each prediction so regressions remain reproducible.

## Suggested v1 success gates

Do not lock hard thresholds until the first corpus is measured. After the baseline exists, establish per-arrangement targets and regression tolerances. The preferred release gate should combine musical metrics with editing-time improvement rather than optimizing F1 alone.
