# EOF Upstream and Fork Inventory

Issue: #414  
Program: `docs/eof-reference-parity-program.md`

## Purpose

Track which Editor on Fire (EOF) repositories and adjacent Rocksmith tools are worth studying, what evidence makes them relevant, and how they should be used.

This inventory is deliberately evidence-based. A repository being a fork does not mean it contains useful divergent work. Mirrors, stale snapshots and platform-only forks should not consume the same audit effort as active domain-specific branches.

## Primary EOF upstream

### `raynebc/editor-on-fire`

**Role:** primary current EOF reference implementation  
**Default branch:** `master`  
**License:** BSD-style 3-clause (`license.txt`)  
**Audit priority:** P0

Why this is primary:

- active in August 2026;
- recent commits continue to modify Guitar Pro import, timing-sensitive note truncation, ties, slides, handshapes, FHP/fingering warnings and Rocksmith arrangement behavior;
- source contains dedicated Rocksmith and Guitar Pro implementation areas such as `src/gp_import.c/.h`, `src/rs.c/.h`, `src/rs_import.c/.h`, `src/beat.c/.h`, `src/bf.c/.h` and related song/track helpers;
- root license permits modification and redistribution with attribution/conditions preserved.

Recent commit themes observed during program creation include:

- GP short-note/chord truncation fixes;
- handling when the first beat is not at 0 seconds;
- tied-note import changes;
- shift/unpitched/legato slide behavior;
- GP note endpoint resnapping for millisecond rounding;
- FHP/handshape violation explanations;
- fingering behavior for muted notes;
- arpeggio/handshape rendering and behavior;
- Rocksmith arrangement metadata behavior.

**Policy:** inspect this repository first for mature domain behavior unless a more specialized reference is clearly better for the subsystem.

## Historical/reference snapshots

### `Berneer/editor-on-fire`

**Role:** historical snapshot/reference  
**Audit priority:** P2 except where already cited by existing work

This snapshot was the source inspected during the Product Reality timing investigation that led to PR #413. It remains useful for provenance of that work, but new audits should normally start from `raynebc/editor-on-fire` so later fixes are not missed.

### `cincodenada/editor-on-fire`

**Role:** historical fork/manual/reference material  
**Audit priority:** P2

Useful for historical documentation and cross-checking older implementation behavior. Do not assume it represents current EOF behavior.

## High-priority forks

### `xmist001/editor-on-fire-automated`

**Role:** high-value divergent/automation-oriented fork candidate  
**Audit priority:** P0 for GP/timing/automation-related work

Recent 2026 commits found during the initial inventory include:

- refactoring Guitar Pro allocation/cleanup paths;
- rewriting GP triplet-feel handling;
- separating GPA sync application logic;
- adding a leading-silence option that can automatically create a Rocksmith COUNT measure and tick events;
- preserving optional GP ghost-note status for guitar/bass;
- tempo-map validation improvements;
- Songsterr timing import support;
- GP slide and note-length fixes;
- FHP and handshape-related fixes.

This makes the fork directly relevant to this project's automation goal.

**Audit questions:**

1. Which commits are unique to this fork versus later incorporated into primary EOF?
2. Which automation-oriented behaviors can become deterministic non-GUI functions in our pipeline?
3. Which GP/timing changes are later superseded by `raynebc`?
4. Are there useful tests or validation rules we can port independently?

### `yourdj/editor-on-fire`

**Role:** likely closely related active mirror/fork  
**Audit priority:** P1 until divergence is established

Initial commit search showed many commits identical to `xmist001/editor-on-fire-automated`. Determine whether this is effectively a mirror, common lineage or contains unique changes before spending implementation time on it.

### `zRocksmith/editor-on-fire`

**Role:** Rocksmith-domain fork candidate  
**Audit priority:** P1

The organization/name makes it potentially relevant, but name alone is not evidence of useful divergence. Compare recent commits/branches to primary EOF before adoption.

### `mlt/editor-on-fire`

**Role:** substantial fork candidate  
**Audit priority:** P1

Repository size suggests a nontrivial history. Audit recent/domain-specific commits before deciding whether it contains unique Rocksmith/GP logic.

### `Jamesllllllllll/editor-on-fire`

**Role:** near-current-size fork candidate  
**Audit priority:** P2 until unique work is proven

Audit for recent commits and divergence only after higher-priority forks.

## Platform-focused forks

### `Desidiosus/editor-on-fire-linux`

**Role:** Linux/build portability reference  
**Audit priority:** P3 for current Windows-first product

Potentially useful for portability/build lessons, but this project's primary platform is Windows 11. Do not let platform-only differences displace authoring-semantic work.

## Other forks discovered in initial search

The initial GitHub repository search also surfaced numerous `editor-on-fire` forks, including examples such as:

- `alex9490/editor-on-fire`
- `destroyer07/editor-on-fire`
- `mrbungle73/editor-on-fire`
- `RoscoeSmith/editor-on-fire`
- `zakkhoyt/editor-on-fire`
- `iurjscsi1101500/editor-on-fire`
- `swedneck/editor-on-fire`
- `zenonasz/editor-on-fire`
- `sswires/editor-on-fire`
- `TheBludell12/editor-on-fire`
- `Audioooo/editor-on-fire`
- `Dansla116/editor-on-fire`
- `Knaifhogg/editor-on-fire`
- `NarrikSynthfox/editor-on-fire`
- `RushOnline/editor-on-fire`
- `miguelSWE/editor-on-fire`
- `iminashi/editor-on-fire`
- `jstma/editor-on-fire`
- `mw2c/editor-on-fire`
- `NewCreature/editor-on-fire`
- `marcaopxt/editor-on-fire`
- `catara/editor-on-fire`
- `zanzo420/editor-on-fire`

These should be triaged with a cheap commit-level screen before any source-level audit.

## Fork triage procedure

For each candidate fork:

1. Record default branch and root license.
2. Inspect the most recent commits.
3. Search commit messages for:
   - Guitar Pro / GP import;
   - Rocksmith / RS export/import;
   - beat / tempo / timing / delay / silence;
   - chord / fingering / FHP / handshape / arpeggio;
   - slide / bend / technique;
   - phrase / section / difficulty;
   - validation / crash / data-loss fixes;
   - automation.
4. Determine whether relevant commits are:
   - already in primary EOF;
   - unique and useful;
   - superseded;
   - platform/UI-only;
   - unrelated.
5. Promote only useful divergence into the subsystem parity matrix.
6. Record exact commit SHAs for any adopted behavior or code.

## Adjacent Rocksmith ecosystem

### `rscustom/rocksmith-custom-song-toolkit`

**Role:** primary mature downstream Rocksmith toolkit reference  
**Audit priority:** P1 after core GP/timing/chord semantics

Initial repository search confirms relevant areas including:

- `RocksmithToolkitLib/XML/Song2014.cs`
- `RocksmithToolkitLib/XML/Song.cs`
- `RocksmithToolkitLib/Sng/Sng2014FileWriter.cs`
- `RocksmithToolkitLib/DLCPackage/Arrangement.cs`
- `RocksmithToolkitLib/DLCPackage/AggregateGraph2014/...`
- `RocksmithToolkitLib/DLCPackage/DDCreator.cs`
- `RocksmithTookitGUI/DDC/DDC.cs`
- `ThirdPartyApps/ddc/...`

This is a strong reference for:

- Rocksmith XML object semantics;
- SNG creation;
- arrangement/package relationships;
- dynamic-difficulty integration/configuration;
- package assembly behavior.

**Important:** audit its license before directly copying code. EOF's BSD license does not apply to this toolkit.

### Toolkit forks

Initial repository search surfaced many forks, including `catara/rocksmith-custom-song-toolkit` and `zRocksmith/rocksmith-custom-song-toolkit` among others.

Fork triage should use the same evidence rule as EOF: recent unique domain fixes first, mirrors later.

## Reference source priority by subsystem

| Subsystem | First reference | Secondary reference |
|---|---|---|
| GP3/4/5 parsing | `raynebc/editor-on-fire` | high-value EOF forks |
| score/beat timing | `raynebc/editor-on-fire` | `xmist001/editor-on-fire-automated` |
| leading silence/count | primary EOF | `xmist001/editor-on-fire-automated` |
| note gaps/sustain | primary EOF | relevant recent forks |
| slides/bends/techniques | primary EOF | recent upstream/fork commits |
| chords/fingering/FHP | primary EOF | EOF forks with FHP fixes |
| phrases/sections/events | primary EOF | toolkit when export semantics overlap |
| RS2014 XML | EOF + toolkit | maintained toolkit forks |
| dynamic difficulty | toolkit/DDC | toolkit forks |
| SNG/package | toolkit + our existing bridge reference | toolkit forks |
| GUI/editor ergonomics | EOF as concept reference | our own Product Reality evidence |

## Inventory maintenance rule

This file should change when:

- a fork is proven to contain valuable unique behavior;
- a fork's unique behavior is merged upstream and no longer needs separate priority;
- a new maintained lineage becomes more authoritative;
- an adjacent tool becomes a better reference for a subsystem;
- licensing changes the allowed reuse strategy.

Do not continuously churn this file for trivial upstream commits. Update it when the reference hierarchy or adoption strategy materially changes.
