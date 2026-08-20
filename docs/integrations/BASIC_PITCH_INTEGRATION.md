# Basic Pitch Integration Guide

## Purpose
Evaluate `spotify/basic-pitch` as an auxiliary polyphonic audio-to-MIDI evidence provider for Rocksmith arrangement verification and alignment research.

## Boundary
Basic Pitch does not become arrangement authority. Human-confirmed GP5/source mapping and Rocksmith-owned timing/review state remain canonical.

## Proposed adapter
Define a replaceable `NoteEvidenceProvider` interface accepting a local audio/stem file plus analysis options and returning normalized candidate events.

Normalized event fields should include:
- start/end time;
- pitch/MIDI note;
- confidence/probability where exposed;
- bend/pitch-contour metadata where usable;
- provider/model/version;
- input/stem hash;
- warnings.

## Evaluation sequence
1. Run Basic Pitch on isolated bass and guitar fixtures.
2. Compare against known MIDI/GP5 ground truth.
3. Evaluate onset timing, pitch accuracy, chord/polyphony behavior, bends, false positives, and missed notes.
4. Repeat on real-song local test material without committing copyrighted audio/results that reveal protected content.
5. Compare direct full-mix analysis versus stem-separated analysis.
6. Measure CPU/GPU/runtime requirements on supported local hardware.

## Intended uses
- second-opinion evidence that a score event is audible;
- identifying likely score/audio mismatches;
- narrowing regions needing human review;
- supporting alignment diagnostics;
- generating candidate corrections that require explicit confirmation.

## Forbidden uses
- automatically replacing score notes;
- silently deleting events that Basic Pitch misses;
- treating confidence as proof of musical correctness;
- allowing model upgrades to change accepted arrangement state without invalidation/review.

## Provenance and invalidation
Evidence must be invalidated when any of these change:
- master audio hash;
- stem hash;
- provider/model/version;
- analysis parameters;
- timebase/transformation authority.

## Acceptance criteria
- Demonstrable improvement in detecting intentional audio/score mismatches on regression fixtures.
- No mutation of canonical arrangements without explicit review.
- Repeatable output for pinned versions/parameters within documented tolerance.
- Clear failure/uncertainty states.
- Adapter can be removed without disrupting normal authoring.

## Rollback
Disable the provider and discard derived evidence. Existing score/timing/provenance state remains authoritative.