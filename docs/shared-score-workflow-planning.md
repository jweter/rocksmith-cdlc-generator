# Shared-score workflow planning

The project workflow planner now treats the registered complete score and its fan-out manifest as first-class project state instead of discovering only generic imported Bass JSON.

## Planning contract

When no complete score is registered, shared-score authoring remains optional and the existing audio-first Bass path can continue.

When a score is registered, the planner verifies the stored score through the existing immutable score contract. Proposed Bass, Lead, or Rhythm mappings remain human blockers until explicitly confirmed. Importer confidence never substitutes for source acceptance.

After the score's rights/provenance review is resolved and all currently proposed role mappings are human-confirmed, the planner exposes `cdlc-score-fanout PROJECT` as an automatic ready step.

The step is considered complete only when the authoritative `score-fanout-<sha>.json` manifest matches the current score hash, source format, and complete set of human-confirmed role-to-track mappings, and every referenced arrangement JSON still exists and matches its role, source track index, and score provenance hash.

A missing, stale, malformed, or mismatched fan-out artifact makes fan-out ready again rather than silently treating stale arrangement data as authoritative.

## Safety boundary

This planning change is read-only. It does not confirm musical mappings, elevate provenance, choose tones or fingering, align notes to audio, or package Rocksmith output. Those remain independent automatic or human-reviewed stages.

The next architectural slice can use this authoritative arrangement set to build one shared recording/score timing state, then allow Bass, Lead, and Rhythm to consume that timing without independently rediscovering the song structure.
