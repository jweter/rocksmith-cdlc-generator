# Product Reality session evidence schema

Product Reality evidence is local diagnostic data. It records only hashes/format metadata needed to identify the tested project inputs, plus measured workflow evidence entered during the session.

## Session identity

Each session stores:

- a generated session UUID;
- registered recording SHA-256 and recording duration;
- registered score SHA-256 and format when present;
- an optional packaged build/artifact identifier supplied by the tester;
- start/completion timestamps and explicit final PASS/FAIL reason.

It intentionally does not copy commercial audio, score bytes, source paths, project titles, CFSM exports, Ubisoft-derived data, PSARC packages, or Rocksmith installation data into the report.

## Timings

Stage records contain a name, start/completion timestamps, measured elapsed seconds, and whether that interval counts toward human editing time.

The reported editing-minutes-per-finished-minute metric is calculated from measured editing intervals divided by the registered recording duration. It is not estimated after the session.

## Corrections

Correction counts are grouped independently for Bass, Lead, and Rhythm by:

- timing;
- physical position;
- technique;
- chord fingering;
- chord identity;
- other.

These counters are observation evidence only. They do not create, modify, or accept arrangement authority.

## Observations

Each observation records an area, severity (`note`, `friction`, or `blocker`), free-text evidence, timestamp, and whether the workflow required a CLI or PowerShell workaround.

## Privacy and safety

All generated Product Reality files live beneath the local project's `diagnostics/product-reality/` directory and are gitignored at any project depth.

The recorder cannot modify the live Rocksmith installation or NoCableLauncher and cannot accept source rights, score mapping, timing, positions, techniques, chord identity, tones, validation, or package readiness.
