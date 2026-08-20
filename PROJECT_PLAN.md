# Rocksmith CDLC Generator — Canonical Roadmap

This file is the canonical implementation roadmap. The product goal is a real Windows desktop application that turns one local song recording plus one complete structured score, when available, into reviewed Rocksmith 2014 Bass, Lead, and Rhythm arrangements with as little manual authoring as practical.

The GUI is the primary product. The CLI remains the deterministic engine/debugging surface.

## North-star workflow

```text
Launch Windows app
  → choose local recording + complete score
  → review rights/provenance
  → confirm Bass / Lead / Rhythm mappings
  → analyze recording + fan out score tracks
  → align once
  → review/correct one shared timing model
  → generate three arrangement drafts
  → review notes/chords/fingering/techniques
  → validate
  → metadata / cover / tones
  → Rocksmith XML + DLC Builder handoff
  → build + verify PSARC
  → manual installation
```

## Governing rules

1. Build the Windows product continuously. Defects are recorded as GitHub Issues and do not hijack the roadmap unless they block the normal desktop path, cause reproducible wrong output/data loss, or violate a hard safety boundary.
2. Source media and registered score bytes are immutable identities.
3. One complete score is a project-level musical source, not three independent imports.
4. Bass, Lead, and Rhythm inherit one reviewed score-to-recording timing model whenever the shared-score workflow is used.
5. Human confirmation remains required for uncertain rights/provenance, source mappings, timing acceptance, fingering/playability, tone acceptance, and package readiness.
6. Never invent unresolved guitar string/fret positions or silently turn confidence into authority.
7. Never download/rip streaming-reference media.
8. Never modify the live Rocksmith installation or NoCableLauncher.
9. Never commit commercial audio, private packages, CFSM exports, Ubisoft-derived content, or generated private project data.
10. Packaging remains validation-gated.
11. Passing CI proves the contracts that are tested; it does not by itself prove that the desktop product is usable, responsive, understandable, or efficient for real authoring work.
12. Every claimed capability must be wired through the real product path. Avoid placeholder architecture, fake integrations, unused services, dead dependencies, and documentation claims that exceed demonstrated behavior.
13. Prefer the smallest architecture and dependency set that solves the current product problem. New backends, services, frameworks, dependencies, abstractions, or AI components require a concrete product need and a measurable benefit.
14. Preserve explicit ownership of truth across source → review authority → generated draft → validation → export → package. A downstream artifact must never silently become authoritative when its upstream identity or review authority is stale.
15. As the desktop grows, test the interactive product as well as the deterministic engine: selection, playback synchronization, canvas rendering, editing workflows, blocked-state explanations, and representative end-to-end user actions.
16. Profile representative dense and full-length songs instead of assuming GUI performance. Optimize measured bottlenecks, especially playback-time rendering, large arrangement previews, waveform/timeline drawing, and review navigation.
17. Do not allow the Song Workspace inheritance chain to become an uncontrolled mega-window. Prefer composition/controllers when feature layering begins to make behavior difficult to isolate, test, or reason about.
18. Periodically run an adversarial AI-code audit for dead or duplicate code, unnecessary dependencies, fake wiring, security mistakes, untested interactive behavior, accidental complexity, and capability claims unsupported by real execution.
19. Periodically sweep the repository Issues tab as a deliberate reliability stream. Fix safety/correctness blockers immediately, prioritize high-value normal-path usability/reliability issues alongside roadmap work, and avoid either extreme of ignoring the backlog or letting low-value issues halt product progress.
20. Every open product issue must have an explicit roadmap disposition: current milestone, next hardening milestone, standing engineering practice, later capability expansion, or intentionally deferred. The roadmap should reference issue numbers directly so scheduled development can select them instead of allowing the Issues tab to become a disconnected backlog.

## Product Reality Gate

Feature count is not the product metric. At regular milestones, and before an installable release can be considered ready, run a real lawful song/score case through the packaged Windows application and evaluate the complete user workflow.

The Product Reality Gate must verify or measure:

- launch/open-project reliability on the packaged Windows build;
- recording + complete-score intake and Bass/Lead/Rhythm mapping through the GUI;
- timing review, arrangement navigation, direct event selection, and accepted edits through normal desktop controls;
- playback synchronization and correctness after repeated timing/position/technique edits;
- clarity of stale/blocked states and whether a user can understand what action is required next;
- responsiveness on representative dense/full-length material, including CPU/memory behavior and interaction latency;
- whether normal work can be completed without PowerShell or hidden manual repair steps;
- number and type of human corrections required for Bass, Lead, and Rhythm;
- actual human editing time, recorded during the correction session rather than estimated afterward;
- editing minutes per finished minute as the primary end-user productivity metric;
- successful validation, export, DLC Builder handoff, returned PSARC registration/verification, and manual installation readiness when those stages are in current product scope.

A roadmap milestone may be technically complete while still failing the Product Reality Gate. Product-reality failures become prioritized engineering evidence rather than being dismissed because unit tests pass.

The benchmark corpus and Product Reality Gate complement each other: automated/synthetic benchmarks detect deterministic regressions, while real desktop sessions test whether the whole application is genuinely useful.

## Completed product foundation

Already implemented and reusable:

- immutable local project/audio ingest and FFmpeg normalization;
- beat/tempo analysis and Bass transcription/mapping;
- Guitar Pro 3–5 and MusicXML complete-score intake;
- explicit Bass/Lead/Rhythm track confirmation;
- score fan-out and one shared score-to-recording timeline;
- reviewed timing with loop/slow playback, variable-tempo click, locked anchors, deterministic refit, and explicit promotion;
- Lead/Rhythm drafts inheriting current reviewed shared timing;
- validation/review artifacts and Rocksmith XML authoring;
- DLC Builder staging and PSARC registration/verification;
- packaged Windows desktop executable built in GitHub Actions;
- Song Workspace with project health, arrangement state, review queue, provenance summary, synchronized waveform/timeline, and playback;
- synchronized Bass/Lead/Rhythm score-event preview on the recording clock;
- review-item navigation and tuning-aware virtual fretboard;
- provenance-aware physical string/fret acceptance with Lead/Rhythm draft invalidation;
- direct arbitrary arrangement-event selection with ambiguity-preserving chord-note choice;
- provenance-aware onset/duration acceptance with recording-clock preview overlays and Lead/Rhythm regeneration;
- provenance-aware technique acceptance with preview overlays and Lead/Rhythm regeneration;
- atomic whole-chord Lead/Rhythm fingering acceptance using the existing reviewed-position authority;
- provenance-aware reviewed Lead/Rhythm chord identity with explicit source-event membership and draft staleness binding;
- transactional provenance-aware undo/redo across accepted arrangement review layers with exact restoration and stale-authority refusal.

No unresolved/unverified physical guitar position may pass silently into export.

## Current milestone — Product Reality Gate v1

Before feature accumulation outruns product validation, exercise one representative lawful development song through the packaged Windows application and record a baseline Product Reality report.

### Measurement infrastructure

Provide a separate project-bound Product Reality recorder rather than adding more Song Workspace inheritance. It may record workflow evidence but must own no musical authority.

The recorder should capture:

- packaged build/artifact identity supplied by the tester;
- registered recording/score identity without copying media into reports;
- manually measured workflow stage durations;
- explicit marking of intervals that count as human editing time;
- Bass/Lead/Rhythm correction counts by timing, position, technique, chord/fingering, chord identity, and other work;
- usability/performance observations and whether CLI/PowerShell was required as a workaround;
- explicit final PASS/FAIL plus reason;
- a local JSON evidence record and human-readable Markdown summary;
- editing minutes per finished minute computed from measured editing intervals and recording duration.

Generated Product Reality reports remain local/private project data and must be gitignored.

### Required v1 evidence run

- one reproducible end-to-end session record using a real lawful song + complete structured score;
- timing for major workflow stages and total editing minutes per finished minute;
- Bass/Lead/Rhythm correction counts grouped by timing, position, technique, chord/fingering, and other review work;
- notes on confusing UI states, required workarounds, and any step that still requires CLI/PowerShell;
- responsiveness observations for playback, waveform/timeline drawing, arrangement preview, direct selection, repeated editing, and undo/redo;
- targeted follow-up issues for any normal-path usability, correctness, or performance defect found;
- an explicit pass/fail statement against the current Product Reality Gate, without redefining success after seeing the result.

This milestone is evidence-gathering, not a broad rewrite. Fix normal-path blockers, reproducible wrong output/data loss, and severe responsiveness problems immediately; record lower-severity findings for deliberate follow-up.

After the first Product Reality run, perform an Issues-tab sweep using the new evidence as one prioritization input: close obsolete/duplicate items, repair high-severity correctness/safety defects first, then select the highest-value usability/reliability issues that can be fixed without abandoning forward roadmap progress.

### Roadmap-linked issue queue

The currently open Rocksmith issues are part of the roadmap, not a separate unowned backlog. Scheduled and manual development should keep this queue synchronized with live GitHub state.

1. **#304 — Audit and fix current Product Reality defects before expanding scope.** This is the active defect-remediation umbrella for the current milestone. Reproduce normal-path failures from packaged-app testing, fix blockers and stale/incorrect authority first, add regression protection, and create focused child issues where needed. Do not close the Product Reality milestone while material #304 defects remain unresolved.
2. **#305 — Upgrade the Windows desktop UI to a polished authoring workspace.** Begin after or alongside the evidence-driven #304 remediation pass once the major functional defects are known. Treat this as the first major slice of the following authoring-hardening milestone: audit the running UI, establish a small reusable design system, then improve the primary workflow without weakening provenance, review, or validation gates.
3. **#193 — Track recurring defect patterns and root-cause fixes.** This is a standing engineering-memory obligation across every milestone. Recurring failures discovered through #304, #305, CI, or later Product Reality runs must be cross-linked here with root cause, prevention pattern, and regression coverage rather than repeatedly patched as isolated symptoms.
4. **#46 — Automate Apple Music metadata enrichment for benchmark candidates.** Keep this explicitly scheduled under Later capability expansion. It may proceed only after the normal Windows authoring/build flow is complete enough that metadata enrichment cannot displace core usability/reliability work. Apple Music remains an optional pluggable metadata source, never an audio source or hard runtime/build dependency.

When new issues are opened, assign each one to a roadmap disposition in the same planning cycle. Normal-path blockers and correctness/safety defects can move ahead of later feature work; optional integrations remain behind desktop-product completion unless they become necessary to satisfy a measured Product Reality need.

## Following milestone — Evidence-driven authoring hardening

Use Product Reality Gate evidence and the current GitHub issue backlog rather than speculation to choose the highest-value fixes. #304 remediation findings and #305 are explicit inputs to this milestone, while #193 remains active as the defect-memory layer. Likely areas include:

- complete the bounded Product Reality defect fixes identified under #304;
- execute #305 in evidence-driven slices: UI audit → design-system foundation → highest-value workflow surfaces → regression/smoke coverage;
- confidence/provenance and source-disagreement visualization;
- deliberate integration of reviewed event timing/position/technique overlays into the separate Bass authoring path;
- targeted Song Workspace composition/controller extraction where the inheritance chain demonstrably impedes testing or maintenance;
- targeted canvas/playback rendering optimization for measured dense-song bottlenecks;
- GUI interaction tests for the highest-risk normal user paths;
- high-value open issues whose impact is confirmed by normal-path use or correctness/safety analysis.

Do not perform a broad UI rewrite without measured product evidence. #305 should be delivered incrementally so visual polish and interaction changes remain reviewable and cannot mask functional defects.

## Following milestone — Complete desktop build flow

Bring the remaining end-to-end engine workflow into the GUI:

- three-arrangement validation dashboard;
- metadata and cover art;
- tones and tone regions;
- Rocksmith XML export;
- DLC Builder discovery/project preparation/launch;
- package staging and readiness view;
- returned PSARC registration and integrity verification;
- tool and audio-device diagnostics.

Normal use should not require PowerShell.

## Following milestone — Installable release

- stable versioning;
- branded icon/application metadata;
- GitHub release artifacts;
- installer or equivalently simple Windows distribution;
- first-launch dependency/tool diagnostics;
- user-settings/project migration and recovery behavior;
- optional safe update notification;
- Product Reality Gate passed on representative lawful material with no unresolved normal-path blocker or severe responsiveness defect.

## Later capability expansion

Important, but not allowed to displace completion of the desktop workflow:

- stronger audio-only transcription for songs without structured scores;
- additional score formats through safe adapters;
- richer technique detection;
- dynamic difficulty controls;
- section/phrase inference;
- tone-region detection and Rocksmith device mapping;
- improved source reconciliation;
- batch/project-library tools;
- expanded benchmark suite and recurring real correction-time measurement;
- **#46 Apple Music metadata enrichment for benchmark candidates through an optional pluggable metadata provider; cache only redistributable metadata/provenance and never audio;**
- optional local AI assistance only where it measurably reduces editing time without weakening provenance or human gates.

## Issue policy

When development or Codex review finds an error:

- create/update a GitHub Issue with reproduction context and expected fix direction;
- add or update that issue's explicit roadmap disposition so it cannot become an orphaned backlog item;
- continue the active product milestone by default;
- interrupt immediately for normal-path blockers, reproducible wrong output/data loss, hard safety violations, or severe Product Reality regressions in usability/responsiveness;
- at Product Reality and major milestone boundaries, review the full open Issues tab rather than only newly created issues;
- close or consolidate obsolete/duplicate issues, confirm reproduction where practical, and rank remaining work by safety/correctness, normal-path user impact, frequency, and effort/value;
- deliberately fix a bounded set of highest-value backlog items while continuing roadmap progress instead of allowing the backlog either to stagnate or to consume the entire roadmap;
- cross-link recurring defect classes to #193 and record the root-cause prevention pattern plus regression coverage;
- record lower-value defects for later reliability/hardening passes.

## Success criteria

The project succeeds when a normal Windows user can launch the app, provide a song and score, make the few decisions automation should not make, review/correct Bass + Lead + Rhythm inside the application, and produce a valid Rocksmith CDLC package with materially less authoring effort than a manual workflow.

Success must be demonstrated, not inferred from feature count or CI alone. Representative Product Reality sessions should show that the packaged desktop path is understandable and responsive and that measured editing minutes per finished minute improve meaningfully over the manual baseline.
