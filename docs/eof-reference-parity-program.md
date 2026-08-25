# EOF Reference and Parity Program

Issue: #414

## Purpose

Rocksmith CDLC Generator should not independently rediscover deterministic Guitar Pro and Rocksmith authoring behavior that mature open-source tools already implement correctly.

Editor on Fire (EOF) is now a first-class reference implementation for this project. The goal is not to reproduce EOF's legacy GUI or architecture. The goal is to understand, test, adopt and improve the mature domain logic that makes EOF reliable at Guitar Pro import and Rocksmith authoring, then surround that logic with this project's stronger automation, provenance, confidence, review, validation and Windows workflow.

The program is intentionally long-lived. It applies to every future deterministic authoring subsystem, not only the timing defect that triggered it.

## Why this exists

Product Reality testing found a shared Bass/Lead/Rhythm timing defect where the same Guitar Pro source and recording were correct in EOF but late in Rocksmith CDLC Generator. The resulting investigation found a concrete semantic difference: EOF allows synchronization to put score beats before recording time zero and omits only the pre-zero portion instead of rejecting the valid transform. PR #413 adopted that behavior and added regression protection.

That event established a broader engineering lesson:

> When a mature Rocksmith authoring implementation already handles a domain rule correctly, inspect it before inventing a new rule.

EOF is therefore both:

1. a **behavioral oracle** for same-input comparisons; and
2. a **BSD-licensed donor/reference implementation** for algorithms and source that are useful to this project.

## Reference hierarchy

### Tier 1 — primary EOF upstream

**`raynebc/editor-on-fire`** is the primary current reference lineage.

As of the creation of this program, its recent 2026 history includes changes to:

- Guitar Pro import timing and short-note/chord truncation;
- GP tied notes;
- slide semantics;
- sustain/gap behavior;
- FHP and handshape validation;
- fingering behavior;
- Rocksmith arrangement metadata;
- arpeggio/handshape behavior;
- Rocksmith panels and authoring warnings.

This is not an abandoned historical codebase. It is active domain knowledge and should be treated accordingly.

### Tier 2 — high-value EOF forks

Forks are evidence sources, not automatically better than primary upstream. A fork is promoted in audit priority when it has recent, domain-relevant divergent work.

Initial high-priority candidate:

- **`xmist001/editor-on-fire-automated`** — recent 2026 commits explicitly include Guitar Pro import refactoring, triplet-feel import changes, GPA timing separation, leading-silence/COUNT-measure automation, GP ghost-note handling and additional Rocksmith-adjacent automation work.

Other forks found in the GitHub fork/repository search that warrant inventory comparison include:

- `yourdj/editor-on-fire`
- `zRocksmith/editor-on-fire`
- `mlt/editor-on-fire`
- `Desidiosus/editor-on-fire-linux`
- `cincodenada/editor-on-fire`
- `Berneer/editor-on-fire`
- `Jamesllllllllll/editor-on-fire`
- other forks discovered by the inventory pass

The audit must distinguish true divergent work from mirrors or stale snapshots. Repository size or recency alone is not enough to adopt code.

### Tier 3 — adjacent Rocksmith toolchain

EOF is not the entire authoring/build ecosystem. The program also studies mature adjacent implementations where they cover downstream semantics better than EOF itself.

Primary adjacent reference:

- **`rscustom/rocksmith-custom-song-toolkit`**
  - Rocksmith 2014 XML models;
  - SNG writing;
  - arrangement/package structures;
  - dynamic-difficulty creator integration and configuration;
  - DLC package generation concepts.

Relevant maintained or divergent toolkit forks may also be audited when they contain unique fixes.

The project already has its own packaging and PSARC bridge work. Studying the toolkit does not automatically replace that architecture; it gives us another mature correctness reference.

## Licensing and provenance policy

EOF's primary project code is distributed under a BSD-style 3-clause license. That permits source/binary redistribution and modification provided the copyright notice, conditions and disclaimer are retained and contributor names are not used for endorsement without permission.

Accordingly, this project may:

- study EOF behavior;
- reproduce algorithms;
- port C logic into Python;
- adapt substantial functions where that is the cleanest implementation;
- retain direct source fragments when useful and license-compatible;
- improve the adopted behavior after parity is demonstrated.

Requirements:

1. Record the upstream repository, path and preferably commit/SHA for substantial direct adaptations.
2. Preserve required license attribution in `THIRD_PARTY_NOTICES.md` and/or source headers where appropriate.
3. Review the license of any vendored/third-party subtree before copying from it. EOF's root license does not automatically cover bundled dependencies.
4. Do not assume the Rocksmith Custom Song Toolkit or any other adjacent project has the same license as EOF; inspect its license before direct code reuse.
5. Do not commit copyrighted song audio, private score/tab files, Ubisoft-derived assets or other restricted test material merely to make differential testing convenient.

## Core engineering rule

Before implementing or materially changing deterministic domain logic in any of the following areas, the implementation PR should answer:

> What does EOF or another mature Rocksmith reference implementation do here?

If the mature implementation has no relevant behavior, say so. If our behavior intentionally differs, document why.

This applies to:

- Guitar Pro parsing and unwrapping;
- score/beat timing;
- note durations and gaps;
- techniques;
- chord/fingering logic;
- fret-hand positions;
- handshapes/arpeggios;
- phrases and sections;
- difficulties;
- Rocksmith XML validation/export;
- SNG/package/DDC behavior.

## Adoption model

There are four allowed outcomes for an audited EOF behavior.

### 1. PARITY

Our implementation should match EOF because EOF's behavior is correct and appropriate.

Action:

- create a deterministic regression/oracle test;
- port/adapt the behavior;
- prove the same input produces equivalent relevant output.

### 2. PARITY + IMPROVEMENT

First reproduce the mature behavior, then deliberately improve it.

Examples:

- EOF requires a manual correction but exposes a deterministic rule we can automate;
- EOF performs correct validation but our application can surface clearer recovery guidance;
- EOF handles one score source while our architecture can preserve multiple provenance-aware candidates.

The parity baseline prevents the improvement from accidentally discarding mature correctness.

### 3. LEARN ONLY

EOF's implementation is useful context but not suitable for our architecture or product.

Examples:

- Allegro GUI rendering;
- menu plumbing;
- mutable editor-state architecture that conflicts with our authority model.

Record the lesson but do not port the implementation.

### 4. INTENTIONAL DIVERGENCE

Our behavior should differ for a documented product reason.

Examples:

- stronger provenance requirements;
- fail-closed human-review boundaries;
- non-destructive project-state behavior;
- automated confidence handling;
- safer packaging authority.

A divergence must identify the reference behavior and the reason for departing from it.

## Phased execution plan

### Phase 0 — establish the program

Deliverables:

- issue #414 as the standing work tracker;
- this program document;
- `docs/eof-subsystem-parity-matrix.md`;
- `docs/eof-upstream-fork-inventory.md`;
- roadmap and autonomous-development policy integration;
- current third-party attribution corrected to distinguish the active upstream lineage from the historical snapshot used by #413.

Exit gate:

- future autonomous runs know to inspect mature references before inventing deterministic authoring behavior.

### Phase 1 — Guitar Pro + timing core

Highest priority because errors here contaminate every arrangement and every downstream review step.

Audit:

- GP3/GP4/GP5 parser behavior;
- tempo maps and time signatures;
- measure-to-beat conversion;
- leading rests/count-ins/pre-roll;
- chart delay;
- repeats and alternate endings;
- coda/segno/fine unwrapping;
- tied notes;
- note durations;
- staccato/gap/truncation behavior;
- endpoint resnapping/rounding;
- triplet feel;
- GP-version quirks and invalid notation recovery.

Reference files are expected to include EOF's `src/gp_import.c/.h`, `src/beat.c/.h`, relevant song/track helpers and fork variants.

Exit gate:

- the parity matrix has explicit status for every Phase 1 row;
- known same-input discrepancies are either fixed, intentionally divergent or tracked with a concrete reason;
- regression fixtures cover each adopted behavior.

### Phase 2 — techniques and note semantics

Audit:

- hammer-on/pull-off;
- tapping;
- palm mute;
- harmonics;
- tremolo picking;
- vibrato;
- bends and bend curves;
- slide-in, pitched, unpitched, shift and legato slide semantics;
- link-next behavior;
- ghost/muted notes;
- string/fret preservation;
- tuning/capo handling.

Exit gate:

- imported technique semantics can be compared deterministically against EOF fixtures;
- no technique is silently lost or invented during GP → internal model → Rocksmith export.

### Phase 3 — chords, fingering, FHP and handshapes

Audit:

- chord templates and identity;
- chord naming where relevant;
- fingering inference and validation;
- fingerless/muted-note handling;
- fret-hand positions;
- FHP width/range rules;
- handshape/arpeggio generation;
- chord slides and handshape transitions;
- violations/warnings.

Reference files are expected to include EOF's `src/rs.c/.h`, `src/rs_import.c/.h`, `src/bf.c/.h`, `src/song.c/.h`, relevant track/menu logic and recent upstream commits.

Exit gate:

- our generated chord/FHP/handshape state is parity-tested or intentionally divergent;
- Product Reality correction burden for fingering/position is measured before and after adoption slices.

### Phase 4 — phrases, sections, difficulties and Rocksmith events

Audit:

- Rocksmith section vocabulary;
- phrase boundaries;
- COUNT behavior;
- event/tick behavior;
- arpeggio/handshape phrases;
- tremolo phrases;
- difficulty population;
- dynamic-difficulty assumptions;
- phrase/section constraints and export warnings.

Exit gate:

- deterministic phrase/section behavior is testable without manual inspection alone;
- dynamic difficulty has a documented reference model before we invent one.

### Phase 5 — Rocksmith XML and downstream build semantics

Audit EOF plus Rocksmith Custom Song Toolkit:

- Rocksmith 2014 XML models;
- notes/chords/chord templates;
- levels/difficulties;
- phrase iterations;
- sections/events;
- arrangement metadata;
- XML validation assumptions;
- SNG generation;
- dynamic-difficulty creator behavior/configuration;
- package/aggregate graph behavior where relevant.

Exit gate:

- our XML/SNG/package stages have a documented mature-reference comparison;
- differences are regression-tested or explicitly justified.

### Phase 6 — automate beyond the reference tools

Once deterministic parity is strong, use this project's architecture to go further:

- automatically choose/qualify score sources;
- reconcile score timing against recording evidence;
- compare multiple lawful score candidates;
- identify likely wrong source versions;
- auto-map arrangement roles;
- infer or validate sections/phrases;
- auto-propose fingering/FHP corrections;
- self-diagnose mismatches;
- route only real ambiguity to humans;
- measure editing minutes per finished minute.

EOF parity is the floor, not the ceiling.

## Differential/oracle test design

### Fixture categories

Use three kinds of fixtures.

#### Synthetic fixtures

Small generated scores/audio where exact expected behavior is known and redistributable.

Best for:

- timing;
- tempo changes;
- repeats;
- ties;
- techniques;
- chord/FHP rules.

#### Redistributable reference fixtures

Public-domain/original/explicitly licensed source material that may legally live in the repository.

Best for broader end-to-end coverage.

#### Private Product Reality fixtures

Real commercial songs and personal score files remain local/private. Store only media-free observation metadata when appropriate.

Best for proving that synthetic parity survives real material.

### Comparison levels

For the same logical source, compare:

1. beat/downbeat positions;
2. note onset and endpoint;
3. pitch;
4. string/fret;
5. chord membership;
6. fingering;
7. FHP/handshape;
8. techniques;
9. phrases/sections/events;
10. exported Rocksmith XML semantics.

Not every subsystem needs byte-for-byte equality. Tests should compare semantic output at the level that matters to Rocksmith.

### Tolerances

Timing tolerances must be explicit by test class. Do not hide systematic offsets behind broad tolerances. For deterministic imported score timing, use strict millisecond-scale tolerances unless a format/rounding rule requires otherwise.

## Upstream commit-watch policy

EOF is active. The audit is not a one-time snapshot.

At meaningful Rocksmith milestones or before changing an already-audited subsystem:

- inspect recent `raynebc/editor-on-fire` commits touching that subsystem;
- inspect high-priority forks for relevant divergent work;
- update the inventory when a fork becomes materially more or less useful;
- pull new regression ideas from upstream bug fixes even when we do not copy the implementation.

Recent upstream commit messages are especially valuable because they reveal years-old edge cases that may not be obvious from function names alone.

## Prioritization

Rank adoption work by this order:

1. wrong timing or wrong musical output affecting all arrangements;
2. data loss or silent technique/chord corruption;
3. Rocksmith validation/export correctness;
4. high-frequency human correction burden;
5. performance bottlenecks on full-length songs;
6. lower-value editor convenience behavior.

A large amount of reusable EOF logic does not justify a big-bang rewrite. Port behavior in small, independently testable slices.

## Definition of done for an audited subsystem

A matrix row can be marked complete only when it records:

- mature reference repository/path;
- our corresponding module/path;
- observed behavior and important edge cases;
- parity state;
- reuse decision;
- license/provenance note where code was directly adapted;
- regression coverage or a tracked gap;
- Product Reality impact if applicable.

## Long-term target

The target is not “EOF rewritten in Python.”

The target is:

> Mature EOF/Rocksmith authoring correctness + modern deterministic testing + automated source/audio reconciliation + provenance-aware review + modern Windows UX + one-click Bass/Lead/Rhythm production.

When this program succeeds, EOF becomes the accumulated expert knowledge underneath the pipeline rather than a separate manual tool the user needs to understand or operate for normal use.
