# Private Rocksmith Library Regression Corpus

Issue: #693
Roadmap role: standing verification program / current Product Reality automation support

## Purpose

Use the user's existing installed Rocksmith library as a **private, local benchmark and regression corpus** for real-world differential testing of the Rocksmith CDLC Generator.

The corpus exists to answer questions a computer can measure without requiring repeated manual laptop testing. It complements, rather than replaces:

- repository-native unit/integration/golden tests;
- EOF and mature-tool differential parity;
- the Private Local Product Reality Runner;
- occasional human judgment for genuinely subjective musical feel, fingering quality, tone preference, or ambiguous source interpretation.

The central rule remains:

> **Zero humans for facts a computer can measure.**

## Privacy and rights boundary

The installed library contains material that may include commercial audio, official DLC/PSARC packages, custom DLC, Ubisoft-derived content, and other material that is not appropriate for a public repository or public CI artifact.

Therefore:

1. The live Rocksmith installation is **read-only source evidence**. Never modify it.
2. Build a separate private mirror/staging corpus outside the repository and outside the live Rocksmith directory.
3. Keep raw PSARC/DLC packages, commercial audio, extracted Ubisoft-derived assets, CFSM exports, private score/tab files, and generated private workspaces local to the user's Windows machine.
4. Never commit or upload those restricted/raw files to this public GitHub repository.
5. The unattended worker may publish only **sanitized derived evidence**, such as:
   - SHA-256/content hashes;
   - exact Git/build identity;
   - arrangement counts and categories;
   - trust tier;
   - timing deltas and drift metrics;
   - pitch/onset/duration agreement metrics;
   - sanitized structural-validation findings;
   - aggregate pass/fail statistics;
   - non-copyrighted failure signatures and diagnostics.
6. Local paths should be redacted from uploaded diagnostics where practical.
7. If a comparison requires restricted source bytes, it runs only on the private Windows worker.

The private corpus is an evaluation source, not a redistribution mechanism.

## Trust tiers

Do not assume every installed arrangement is authoritative.

### Tier A — Official Rocksmith arrangements

Highest-trust reference material for:

- Rocksmith timing semantics;
- arrangement presence and structure;
- tuning/capo metadata;
- phrases/sections/events;
- package/manifests and supported Rocksmith semantics;
- mature note/chord/technique authoring behavior where the official chart is relevant to the test.

Tier A remains a reference, not training authority for claims of independent generalization.

### Tier B — User-trusted high-quality CDLC

Custom arrangements the user or project has explicitly promoted as good reference material.

Useful for:

- broader song/style coverage;
- alternate tunings;
- techniques not well represented in Tier A;
- difficult/edge-case arrangements;
- practical authoring conventions.

Tier B results must remain distinguishable from Tier A.

### Tier C — Unverified installed content

Default category for unknown/custom packages.

Use for:

- compatibility testing;
- parser/package robustness;
- unusual metadata/tunings;
- stress/performance testing;
- discovery of candidate edge cases.

Tier C must not silently become musical ground truth.

## Private mirror layout

Recommended local layout, configurable and never hard-coded to one user's path:

```text
<private-test-root>/
  rocksmith-library-corpus/
    source_inventory/
      inventory.json
      copy_manifest.json
    packages/
      official/
      trusted_cdlc/
      unverified/
    extracted/
      <content-hash>/
    manifests/
      corpus_manifest.json
      trusted_overrides.json
    results/
      <git-sha>/
    cache/
```

The copy/mirror process must:

- discover or configure the live Rocksmith DLC directory;
- copy into private staging, never in-place modify;
- use hashes to skip unchanged files;
- record source size, mtime, hash, copy timestamp, and destination identity;
- detect interrupted/partial copies;
- support safe incremental refresh;
- fail closed on hash mismatch;
- never delete from the live library;
- avoid automatic deletion from the private corpus unless a separate safe retention policy is implemented.

## Inventory and catalog

Prefer existing local metadata when reliable, including CustomsForge Song Manager catalog data, while keeping raw exports private.

The private manifest should normalize only the fields needed for testing, for example:

```json
{
  "corpus_schema_version": 1,
  "package_hash": "sha256:...",
  "trust_tier": "A",
  "source_kind": "official_rocksmith",
  "artist": "...",
  "title": "...",
  "arrangements": ["bass", "lead", "rhythm"],
  "tunings": ["E Standard"],
  "duration_seconds": 247.3,
  "private_package_path": "<redacted/local>",
  "reference_status": "eligible"
}
```

Artist/title may remain local-only if later privacy policy decides they should not appear in uploaded evidence. The benchmark engine should work from a stable corpus ID/hash regardless.

## Reference extraction

Build a private adapter that can normalize comparison-relevant data from a selected package without turning extracted content into committed fixtures.

Potential normalized reference fields:

- arrangement type;
- tuning/capo;
- beat/measure/tempo lattice when available;
- first playable event;
- note/chord pitch content;
- onset and duration;
- string/fret position;
- techniques;
- phrases/sections/events;
- COUNT/END and other Rocksmith structural markers;
- package/manifests needed for structural validation.

Reference extraction must preserve:

- source package hash;
- extractor/tool version;
- extraction timestamp;
- provenance to the private package;
- trust tier.

## Differential comparison model

Exact identity is not always the correct acceptance criterion. Compare at several layers.

### Timing / phase

Measure:

- first playable event delta;
- beat-space phase error;
- measure/bar displacement;
- median/max event timing error;
- timing delta spread;
- cumulative drift over the song;
- section/phrase boundary displacement;
- Bass/Lead/Rhythm shared-transform consistency.

A constant multi-beat or multi-measure displacement should be classified explicitly rather than hidden inside aggregate timing error.

### Pitch / musical identity

Measure:

- pitch-event agreement;
- chord pitch-set agreement;
- missing/extra events;
- note-order/phrase continuity;
- repeated-riff agreement where appropriate.

### Duration / sustain

Measure:

- note-off/duration delta;
- sustain crossing into known rests;
- tied/continued-note semantics;
- gap/overlap violations.

### String/fret mapping

Treat this separately from pitch identity.

Two charts may be musically equivalent while using different valid fretboard positions. Therefore report:

- exact string/fret agreement;
- pitch-equivalent alternate mapping;
- impossible/out-of-range mapping;
- excessive position-jump/playability diagnostics.

Do not fail a candidate solely for using a different physically valid fingering unless the benchmark specifically tests fingering parity.

### Techniques and structure

Measure separately:

- bends/slides/HOPO/vibrato/palm-mute/harmonic/etc. when represented;
- phrase/section/event identity;
- tuning/capo;
- COUNT/END and packaging structure;
- arrangement presence and Bass/Lead/Rhythm symmetry.

Technique agreement should carry confidence/tolerance because mature sources can legitimately differ in authoring judgment.

## Representative corpus design

The private corpus may contain hundreds of installed packages, but normal regression should select a balanced subset.

Desired categories include:

- simple eighth-note bass;
- melodic bass;
- syncopated bass;
- fast picked bass;
- distorted bass;
- slides and sustain-heavy bass;
- sparse single-note lead;
- bends/slides/technique-rich lead;
- power-chord rhythm;
- dense chord rhythm;
- standard tuning;
- Drop D / lower tunings;
- tempo-stable studio recordings;
- tempo-change or live/drifting material where supported;
- sparse and dense/full-length arrangements;
- early entrances, long intros, pickup measures, and repeated-riff ambiguity.

Selection should be deterministic from an explicit manifest rather than depend on filesystem ordering.

## Fast and scheduled lanes

### Fast private regression

Use short locally extracted segments or selected deterministic checkpoints where lawful and technically useful.

Purpose:

- timing-phase regressions;
- first-note regressions;
- chord/pitch mutation detection;
- parser/export invariants;
- quick pre-promotion checks.

### Scheduled full-song regression

Run full representative songs on the idle Windows worker.

Purpose:

- drift detection;
- long-range timing behavior;
- dense-arrangement performance;
- full structure/section/phrase checks;
- package and Product Reality qualification.

Full-song commercial/restricted data never leaves the private worker.

## Worker result contract

Every run should bind results to:

```text
repository
branch
exact Git SHA
packaged build/artifact identity
generator version
Python version
FFmpeg version
model names/versions when applicable
reference extractor version
source/reference hashes
corpus manifest version
run timestamp
```

Allowed result states:

- `PASS`
- `FAIL`
- `REVIEW_REQUIRED`
- `ENVIRONMENT_FAILURE`

A failed or unavailable reference must not be converted to PASS by omission.

## Example sanitized result

```text
PRIVATE LIBRARY REGRESSION
Git SHA: <sha>
Corpus manifest: v1 / <hash>
Tier A songs: 12
Tier B songs: 8
Arrangements compared: 47

Timing phase:            47/47 PASS
Full-song drift:         47/47 PASS
Pitch-event agreement:   96.8% aggregate
Chord pitch-set match:   95.4% aggregate
Equivalent fret mapping: 93.1% aggregate
Technique agreement:     87.0% aggregate
Structural validation:   47/47 PASS

Regression:
  corpus_case: A-009
  arrangement: bass
  classification: CONSTANT_PHASE_OFFSET
  displacement: +4 beats
  prior accepted build: PASS

RESULT: FAIL
```

The public/remote evidence should not contain copyrighted note streams, extracted audio, full song XML, or restricted package content.

## Mutation tests

Before trusting the differential lane, prove that it detects deliberate defects.

Minimum mutation set:

1. shift all arrangement events by one beat;
2. shift by one full measure;
3. introduce post-tempo-change drift;
4. mutate one note pitch;
5. mutate one note inside a chord;
6. alter sustain duration across a known rest/gap;
7. remove one arrangement;
8. alter tuning metadata;
9. where technique parity is enabled, mutate one supported technique.

A comparator that cannot detect the relevant mutation is not evidence for that defect class.

## Relationship to EOF parity

EOF differential fixtures remain the mature-tool semantic oracle for deterministic authoring behavior that can be represented safely in committed synthetic/media-free fixtures.

The private installed-library corpus adds a separate real-world reference lane:

```text
synthetic deterministic fixtures
        +
EOF/mature-tool same-input differential tests
        +
private official/trusted Rocksmith library corpus
        +
unattended packaged Windows Product Reality
        ↓
stronger evidence than any one lane alone
```

Do not use the private corpus as an excuse to stop building small reproducible repository-native regressions. When a private corpus run finds a deterministic defect, reduce it to a safe synthetic/public regression fixture whenever practical.

## Human involvement

The system should not ask the user to manually compare timestamps, count bars, inspect deterministic package metadata, or rediscover repeatable timing errors once the private corpus lane can measure them.

Human input is appropriate for:

- initially promoting selected CDLC to Tier B;
- source/rights decisions that automation cannot establish;
- subjective fingering quality;
- tone preference;
- genuinely ambiguous musical interpretation;
- optional milestone gameplay acceptance.

Even then, the worker should prepare the exact comparison/evidence so the user answers only the irreducibly human question.

## First implementation milestone

The first bounded implementation should be:

1. discover/configure the installed Rocksmith DLC directory;
2. create/refresh a private hashed mirror outside the repo and live game directory;
3. inventory packages and classify at least official vs custom without mutating them;
4. choose one Tier A song containing Bass + Lead + Rhythm;
5. extract a private normalized reference;
6. compare generator output against the reference for first playable event, beat-phase/timing drift, arrangement presence, and pitch/chord identity;
7. prove deliberate phase and note/chord mutations are detected;
8. emit a sanitized machine-readable and Markdown report tied to exact Git/build identity;
9. run the lane unattended on the approved Windows worker.

Only after this works should corpus breadth and technique/fingering metrics expand.

## Acceptance criteria

The program is considered established when:

- the private library mirror can be refreshed incrementally and safely;
- the live Rocksmith installation is never modified;
- every corpus package has a stable hash and trust tier;
- at least one Tier A Bass/Lead/Rhythm package participates in an unattended generator-vs-reference differential run;
- deliberate timing and note/chord defects are caught;
- no restricted source bytes enter Git or public CI artifacts;
- results are reproducible against exact build/reference identities;
- private failures can be reduced into safe repository-native regressions when practical;
- Jeremy is no longer asked to rediscover deterministic timing/reference discrepancies that the lane can measure.
