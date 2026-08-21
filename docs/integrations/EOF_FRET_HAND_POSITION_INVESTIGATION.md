# EOF fret-hand-position investigation

## Purpose

Define the evidence needed to use Editor on Fire (EOF) as an optional reference for future global fretboard-position optimization without promoting EOF to canonical authority.

This document is an investigation contract, not an implementation of an optimizer and not an acceptance shortcut.

## Current repository behavior

The current reviewed-position path already enforces several hard invariants:

- reviewed string/fret placement remains the canonical physical-position authority;
- every accepted note position must reproduce the source MIDI pitch under the current source tuning;
- chord fingering acceptance is atomic for one simultaneous chord;
- two notes in one accepted chord cannot occupy the same string;
- stale preview/fan-out/score authority is rejected rather than silently reused;
- human fingering/playability review remains a gate.

What the repository does not currently define is a global objective that chooses among multiple pitch-correct position sequences across time.

## Why EOF is useful here

EOF can serve as a mature external comparison surface for how a Rocksmith-oriented authoring tool places or validates fret-hand positions. Its output is evidence only. A match does not prove that the project should copy EOF, and a mismatch does not prove the project is wrong.

The investigation should answer which observable constraints appear stable enough to become candidates for project-owned optimization rules.

## Evidence questions

For the same lawful source material, tuning, arrangement, and note sequence, record:

1. **Anchor / hand-position placement**
   - where EOF places or requests fret-hand positions;
   - when positions change;
   - whether changes align with phrases, chords, large fret jumps, or local note density.

2. **Span tolerance**
   - largest fret span EOF accepts without changing hand position;
   - behavior around open strings mixed with fretted notes;
   - behavior around repeated notes on alternate strings.

3. **Transition cost**
   - whether EOF prefers fewer position changes even when another pitch-correct mapping exists;
   - treatment of large instantaneous shifts;
   - treatment of short-lived excursions away from an established hand region.

4. **Chord constraints**
   - whether one hand position is expected to cover all notes in a simultaneous chord;
   - how stretches and barre-like shapes affect the chosen position;
   - whether otherwise pitch-correct but impractical fingerings are flagged.

5. **Lead / Rhythm / Bass differences**
   - whether behavior differs by arrangement role;
   - whether Bass tolerates broader shifts or different anchor logic;
   - whether Lead prioritizes melodic continuity differently from Rhythm chord continuity.

6. **Technique interaction**
   - slides, bends, hammer-ons, pull-offs, sustains, palm mutes, and other supported techniques;
   - whether technique semantics constrain valid position transitions beyond pitch correctness.

## Required evidence shape

Any EOF observation used by the repository should be source-bound and reproducible enough to distinguish fact from interpretation. Capture at minimum:

- source score SHA-256 and format;
- source track index and arrangement role;
- tuning;
- EOF version/build identifier;
- note event identities and timing window;
- observed string/fret positions;
- observed fret-hand-position/anchor events when available;
- evidence note describing how the observation was obtained;
- explicit review state (`manual-review-pending` versus independently reviewed).

Private or copyrighted real-song evidence remains outside Git unless redistribution rights explicitly permit otherwise. Synthetic/original fixtures are preferred for committed regression evidence.

## Candidate project-owned optimizer objective

Do not implement this objective until observations justify the terms and weights. A future optimizer should likely treat the problem as constrained sequence optimization rather than independent per-note minimization.

### Hard constraints

Any candidate solution must:

- preserve source MIDI pitch exactly under authoritative tuning;
- use only valid strings and non-negative frets;
- avoid simultaneous collisions where multiple notes require one physical string;
- preserve accepted/reviewed positions as fixed constraints rather than suggestions;
- respect arrangement/source-track identity and current provenance;
- fail closed when required tuning or authority is stale/missing.

### Possible soft costs to measure

Potential cost terms, to be validated rather than assumed:

- hand-position changes;
- magnitude of fret shifts;
- maximum chord stretch;
- short isolated excursions from the local hand region;
- string crossing / position churn;
- technique-breaking transitions;
- departure from already reviewed neighboring positions.

No numeric weights are authorized by this investigation.

## Acceptance criteria for moving from investigation to implementation

A code slice for global fretboard-position optimization is justified only after:

1. at least one original/synthetic fixture demonstrates more than one pitch-correct position sequence;
2. EOF behavior for that fixture is captured with explicit provenance;
3. the project can state which observed behavior it intends to emulate, reject, or merely expose;
4. the proposed hard constraints are covered by deterministic tests;
5. soft-cost choices are documented and independently overridable/testable rather than hidden constants;
6. Bass, Lead, and Rhythm implications are considered separately;
7. existing reviewed-position and human playability gates remain authoritative.

## Non-goals

This investigation does not authorize:

- importing EOF edits into canonical chart state;
- copying EOF source code or algorithms;
- treating EOF-generated fret-hand positions as accepted review decisions;
- auto-accepting fingering because an EOF comparison has zero discrepancies;
- bypassing Bass/Lead/Rhythm human review;
- changing live Rocksmith or NoCableLauncher installations.

## Recommended next experiment

Create one small original GP5 fixture containing deliberately ambiguous pitch-correct choices:

- repeated single-note material playable on multiple strings;
- a compact chord followed by a wide-position chord;
- an open-string passage crossing a hand-position shift;
- one slide or legato transition that constrains physical continuity.

Run the same fixture through the project importer and EOF, capture the observed fret-hand-position behavior, and record the differences without auto-correcting either side. Only then decide whether the first implementation slice should be an anchor inference model, a constrained sequence optimizer, or simply an advisory comparison report.
