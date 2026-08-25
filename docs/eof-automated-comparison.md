# EOF Automated Fork Comparison — Working Study

Tracked by #414.

This document compares `xmist001/editor-on-fire-automated` with current `raynebc/editor-on-fire` and Rocksmith CDLC Generator. It is intentionally evidence-driven and will be expanded as specific subsystems are audited.

## Current conclusion

`xmist001/editor-on-fire-automated` is highly valuable as a donor/reference branch for deterministic Guitar Pro and Rocksmith authoring behavior, especially where its recent work makes mature EOF behavior easier to automate. It is **not** a replacement for this project's Windows GUI, provenance model, review gates, project-state model, or end-to-end automation architecture.

The preferred strategy is selective adoption:

1. use current `raynebc/editor-on-fire` as the primary semantic authority;
2. inspect `xmist001/editor-on-fire-automated` for divergent automation-oriented improvements;
3. port/adapt the better implementation when license-compatible;
4. protect the adopted behavior with parity/differential tests;
5. keep Rocksmith CDLC Generator's stronger product workflow, provenance, stale-state invalidation, and modern GUI architecture.

## High-value areas already identified in xmist001

Recent 2026 history includes:

- Guitar Pro import cleanup that removes duplicated cleanup/error paths;
- rewritten GP triplet-feel handling;
- separation of Go PlayAlong XML sync application from the main GP loader;
- automated leading-silence support with an optional Rocksmith COUNT measure and tick events;
- GP ghost-note import controls;
- improved tempo-map validation/correction;
- Songsterr timing import and chart-delay handling;
- fixes for GP slide notation and technique transfer;
- note-end/marker timing corrections and millisecond-boundary handling;
- performance-oriented replacements for expensive note-count logic;
- Coverity/Cppcheck-driven hardening.

These are prime candidates for focused comparison against our importer, timing, validation, and authoring pipeline.

## What appears better than our current implementation

### Deterministic GP/Rocksmith edge-case coverage

EOF has far more accumulated domain-specific handling for Guitar Pro quirks, Rocksmith note techniques, FHP/handshape rules, phrase/section behavior, note-gap rules, and authoring validation. The automated fork inherits this and adds recent cleanup/automation-oriented improvements.

Our project should assume EOF has the stronger deterministic implementation until a parity test proves otherwise.

### Mature timing/beat-map manipulation

The #413 defect already demonstrated that EOF's beat-map semantics captured an edge case our alignment model mishandled. The automated fork's recent chart-delay, leading-silence, COUNT-measure, triplet-feel, GPA sync and tempo-map work makes it especially useful here.

### Defensive authoring validation

EOF's mature validation and warning logic can expose invalid/ambiguous musical states before export. We should mine these checks and turn as many as practical into deterministic validators and self-diagnostics.

## What does not appear better than our current implementation

### Visual design / UX

The fork retains EOF's legacy C/Allegro desktop/editor architecture. It is not currently evidence that we should replace our Windows authoring UI. Our project should learn workflow concepts and visibility rules from EOF while retaining and improving the modern Song Workspace.

### End-to-end automation architecture

EOF remains an editor centered on a human author. Our goal is a guided pipeline that ingests audio + score, qualifies sources, aligns, derives all three arrangements, surfaces uncertainty, validates, and packages with minimal intervention. That orchestration remains our differentiator.

### Provenance and stale authority

Our immutable source identities, explicit review authority, stale-derived-artifact invalidation, and Product Reality evidence model should remain authoritative even when adopting EOF logic.

## How to decide whether to port a feature

For each candidate feature:

1. locate current upstream EOF behavior and automated-fork divergence;
2. identify applicable license for the exact donor file;
3. create a media-safe fixture or metadata oracle;
4. compare EOF / automated fork / our output;
5. port the behavior if it improves correctness, robustness, performance, or automation;
6. keep our UI/provenance/review boundary around it;
7. add regression and parity tests;
8. record upstream file/commit provenance.

## Initial adoption queue

Priority 0 — finish packaged verification of #413.

Priority 1 — GP + timing semantics:
- triplet feel;
- chart delay / first beat not at zero;
- leading silence + COUNT-measure behavior;
- Go PlayAlong sync-point separation;
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

The target is not an EOF clone. The target is:

> EOF-grade deterministic authoring correctness + automated-fork improvements + our provenance/review architecture + a substantially simpler automated Windows workflow.

That is the route to large gains without discarding the product work already completed.
