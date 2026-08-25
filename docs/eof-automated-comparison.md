# EOF `editor-on-fire-automated` Comparison — Working Study

Tracked by #414.

This document compares `xmist001/editor-on-fire-automated` with current `raynebc/editor-on-fire` and Rocksmith CDLC Generator. It is intentionally evidence-driven and corrects an initial assumption made from the fork name and commit history.

## Important finding: this is not a distinct automation-enhanced EOF lineage

The deeper repository audit established that `xmist001/editor-on-fire-automated` is a direct fork/snapshot of `raynebc/editor-on-fire`, created in May 2026. Its `master` head is commit `a6b81a4edad6f5b48bd455e98111b56fc007a49d`, authored by `raynebc` on 2026-05-21. That exact commit is present in the primary upstream with the same SHA and content.

Therefore the interesting May 2026 commits previously surfaced from the `xmist001` repository — GP cleanup, triplet-feel work, GPA sync separation, leading-silence/COUNT behavior, tempo-map validation and similar changes — are **upstream EOF work**, not proven fork-specific enhancements.

The repository name `editor-on-fire-automated` must not be interpreted as evidence of a separate automated product or a superior automation branch.

## Revised reference decision

1. **Use `raynebc/editor-on-fire` as the authoritative current EOF source.** It contains everything present in the May snapshot plus additional fixes through August 2026.
2. Keep `xmist001/editor-on-fire-automated` only as a historical May-2026 snapshot unless future evidence proves unique branches/commits.
3. Do not spend implementation time porting from the snapshot when the same code exists in current upstream.
4. Continue screening other EOF forks for genuinely unique commits, but require SHA/diff evidence before promoting any fork above P2.

## Why this is actually better news

The features that looked attractive in the automated-named fork are still valuable — they simply belong to current EOF's history. We can study and adopt them from the better-maintained primary source while also receiving later fixes that the May snapshot lacks.

Examples of upstream work relevant to this project include:

- GP import cleanup/error-path hardening;
- rewritten GP triplet-feel handling;
- separation of Go PlayAlong sync application from the main GP loader;
- leading-silence support with an optional Rocksmith COUNT measure and tick events;
- GP ghost-note import controls;
- tempo-map validation/correction;
- Songsterr timing and chart-delay handling;
- GP slide/technique-transfer fixes;
- note endpoint resnapping and millisecond rounding;
- note-gap/truncation and tied-note fixes;
- FHP/handshape validation and clearer authoring diagnostics;
- continued GP/Rocksmith fixes through August 2026.

## What current EOF appears better at than our project today

### Deterministic GP/Rocksmith edge-case coverage

EOF has substantially more accumulated domain-specific handling for Guitar Pro quirks, Rocksmith techniques, note-gap rules, FHP/handshape behavior, phrases/sections and authoring validation. Until parity tests prove otherwise, this project should assume current EOF is the stronger deterministic reference for these rules.

### Mature timing and beat-map manipulation

The #413 Product Reality defect already demonstrated a case where EOF's project-beat semantics handled a valid pre-roll condition that our alignment implementation rejected. Current EOF should be mined systematically for additional timing, chart-delay, first-beat, tempo-map and rounding semantics.

### Defensive authoring validation

EOF contains years of warnings, fixups and edge-case checks. These are strong candidates for conversion into deterministic validators and self-diagnostics in our automated pipeline.

## Where our project should remain ahead

### Visual design / UX

EOF retains a legacy C/Allegro editor UI. It is mature and information-dense, but there is no evidence that it is visually superior to the modern Windows Song Workspace we are building. We should learn from its **information architecture and author feedback**, not copy its visual shell.

### End-to-end automation

EOF remains primarily a human-operated chart editor. Our product goal is recording + structured score → qualification → shared timing → Bass/Lead/Rhythm drafts → targeted review → validation → package with minimal intervention. That orchestration remains our differentiator.

### Provenance and stale authority

Our immutable source identities, explicit review authority, stale-derived-artifact invalidation and Product Reality evidence model remain stronger product constraints and should wrap any adopted EOF logic.

## Speed / performance assessment

There is not yet evidence that current EOF is globally faster than our application or vice versa. The architectures and workloads differ too much for a repository-level claim.

What we can use immediately are **specific performance lessons** from upstream commits: reduced duplicate work, bounded searches, more efficient note-count paths, and mature data-structure choices. Performance adoption should be benchmarked on representative dense/full-length songs before claiming improvement.

## Accuracy assessment

For deterministic Guitar Pro/Rocksmith authoring semantics, EOF currently has the stronger evidence base because:

- the same GP/audio timing case was correct in EOF and wrong in our packaged app before #413;
- EOF has years of explicit fixes for format quirks and Rocksmith constraints;
- current upstream continues fixing these edge cases.

That does not mean every EOF output is automatically ground truth. Our policy is to use differential tests, Product Reality evidence and explicit intentional-divergence decisions.

## How to decide whether to port a feature

For each candidate feature:

1. locate current upstream EOF behavior;
2. check whether any fork has a genuinely unique later/divergent implementation;
3. verify applicable license for the exact donor file;
4. create a media-safe fixture or metadata oracle;
5. compare EOF versus our output;
6. port/adapt behavior if it improves correctness, robustness, performance or automation;
7. preserve our UI/provenance/review boundaries;
8. add regression/parity tests;
9. record upstream file and commit provenance.

## Initial adoption queue

Priority 0 — finish packaged verification of #413.

Priority 1 — GP + timing semantics:
- triplet feel;
- chart delay / first beat not at zero;
- leading silence + COUNT-measure behavior;
- Go PlayAlong sync-point behavior;
- tempo-map validation;
- note endpoint resnapping / millisecond rounding;
- ties/repeats/alternate endings and source beat expansion.

Priority 2 — note-duration and technique correctness:
- truncation/gap rules;
- staccato;
- tied-note length handling;
- shift/legato/unpitched slides;
- slide-in technique transfer;
- bends;
- ghost/muted notes;
- harmonics/vibrato/tremolo/HOPO/tap/palm mute.

Priority 3 — Rocksmith playability semantics:
- chord templates and chord identities;
- fingering inference;
- FHP width/rules;
- handshape/arpeggio rules;
- phrase/section generation;
- Rocksmith-specific warnings and validators.

Priority 4 — downstream artifact parity:
- Rocksmith XML semantics;
- dynamic difficulty / DDC ecosystem;
- SNG/package semantics and diagnostics.

## Product strategy

The target remains:

> Current EOF-grade deterministic authoring correctness + our provenance/review architecture + stronger automation + a substantially simpler modern Windows workflow.

The May `xmist001` snapshot does not change that strategy; the deeper audit simply moves the useful knowledge to its correct source: current `raynebc/editor-on-fire`.
