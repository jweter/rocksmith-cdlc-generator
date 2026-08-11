# Benchmark Corpus

This directory defines the evaluation contract for musical-authoring quality. Do not commit commercial recordings, commercial tablature, or copyrighted Rocksmith packages here. Keep private/local benchmark media outside Git and commit only synthetic/public-domain fixtures or metadata that is legally redistributable.

## Purpose

The benchmark exists to answer one product question: **does the generator produce a draft that is substantially faster to correct than authoring from scratch?**

Each case should have a trusted reference chart and a generated prediction represented as `BenchmarkChart` JSON. The evaluator scores note identity/timing separately from fretboard placement and technique inference so improvements can be attributed to the correct stage.

## Candidate bank

`candidate_bank.yaml` is a ranked research backlog, not a trusted benchmark corpus. It records songs that appear useful for development because they combine musical value, structured-reference availability, and useful engineering characteristics.

The candidate bank deliberately keeps uncertainty explicit:

- `structured_reference.status` says how strongly the existence/quality of structured notation has been verified.
- `dlc_library.status` distinguishes a prior manual no-match from the still-required deterministic full CFSM check.
- `duration_seconds` is null when canonical studio metadata has not yet been verified.
- external catalog metadata is provenance only and is not an audio source.

A candidate may be promoted into the trusted local corpus only after all of the following are true:

1. absence from the current Rocksmith/CFSM library is verified deterministically;
2. a lawful local audio source is available;
3. a lawful structured reference or deliberate human-authored reference is available;
4. the reference is reviewed and explicitly accepted rather than trusted merely because it is structured;
5. a representative 30–90 second excerpt is selected;
6. source hashes, tool/model versions, and relevant configuration are recorded.

`BMARK-001` is reserved for **Lamb of God — Laid to Rest** as the primary end-to-end development candidate. This reservation does not make any external transcription ground truth by itself.

The companion `candidate_bank.schema.json` defines the machine-readable shape. A deterministic validator/CLI should enforce uniqueness, enums, positive known durations, and safe metadata-only paths before this becomes a release gate.

## Golden benchmark ladder

Promote candidates progressively rather than trying to solve the hardest material first:

- **Tier 1 / MVP:** Laid to Rest; Built to Fall; Rose of Sharyn
- **Tier 2 / generalization:** Carrion; Only for the Weak; Twilight of the Thunder God
- **Tier 3 / advanced:** Pull Harder on the Strings of Your Martyr; In Waves; Ritual
- **Tier 4 / stress:** Cirice; Oblivion; Aesthetics of Hate; Halo

This ladder complements, rather than replaces, the smaller synthetic/public-domain fixtures used by automated tests.

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
