# Issue #480 — Pre-promotion timing preview Product Reality fix

## Product Reality failure

A packaged Windows test on 2026-08-30 reached the shared-timeline human gate on the representative lawful GP/audio project. The new page-level Arrangement Preview scrollbar worked, but the user could not see any score-fan-out notes before timing promotion.

The observed state was internally consistent but unusable for the gate:

- Bass draft: current.
- Lead/Rhythm drafts: not built yet because they wait on shared timing.
- Shared timing: not promoted.
- Timeline: recording waveform and detected beats visible.
- Arrangement Preview: unavailable because `analysis/shared_timeline.json` did not exist.
- Validation/review queue: not yet populated.

The product was therefore asking the human to approve a timing transform without showing the musical events produced by that transform.

## Root cause

`load_score_fanout_preview_snapshot()` is a read-only preview path, but it called `alignment_for_role()` for each role. `alignment_for_role()` is intentionally an **authoritative post-promotion** API: it begins by loading `analysis/shared_timeline.json`.

That created a circular gate:

```text
human must inspect note timing
  -> Arrangement Preview requests alignment_for_role()
  -> alignment_for_role() requires shared_timeline.json
  -> shared_timeline.json is written only after human timing approval
  -> human cannot inspect note timing before approving it
```

The exact timing candidate already existed. `build_shared_timeline_candidate()` validates the current recording, registered score, score fan-out, confirmed role mappings, authoritative alignment provenance, authority track, and candidate transform without writing promotion state. The bug was that Arrangement Preview did not use that read-only candidate when promotion had not happened yet.

## Fix

`score_preview.py` now has an explicit preview-only authority resolver:

1. It first asks the existing `alignment_for_role()` for promoted timing. The normal post-promotion path is unchanged.
2. Only if that call fails because no promoted shared-timeline file exists does preview build `build_shared_timeline_candidate()`.
3. The candidate's shared transform is materialized as a role-specific `AlignmentReport` using that role's already-validated fan-out output path and source-track index.
4. No file is written and no human authority is created.
5. If `analysis/shared_timeline.json` **does exist** but the promoted authority is stale/broken, preview still fails closed. It never hides a stale promoted state by silently falling back to a new candidate.

The candidate projection copies exactly the transform fields that promotion would later expose through `alignment_for_role()`:

- method;
- recording and score hashes;
- audio beat start;
- global offset;
- anchor stride/matched beats;
- residual/confidence metrics;
- anchors;
- regions;
- warnings.

Only the role-specific source path and source-track index differ, exactly as they do after promotion.

## Authority / safety boundary

This change is display/read-model only. It does **not**:

- write `shared_timeline.json`;
- mark timing human-confirmed;
- create Lead/Rhythm authoring authority;
- bypass validation;
- change EOF-derived timing semantics;
- change score mapping, provenance, trust, techniques, fingering, packaging, or Rocksmith XML authority.

No new mature-reference behavior is introduced. The implementation reuses the existing EOF-derived alignment candidate and the repository's established shared-timeline semantics from #455/#414.

## Regression protection

`tests/test_score_preview_pre_promotion.py` covers:

- candidate transform materialization with role-specific source identity;
- fallback to the exact candidate when the promoted timeline is absent;
- no `shared_timeline.json` side effect from preview;
- fail-closed behavior when a promoted timeline file exists but its authoritative read fails;
- unchanged promoted-path behavior without candidate construction.

## Packaged acceptance still required

CI can prove the authority-order/read-model behavior but cannot prove the real laptop workflow. After this change is packaged, repeat the same Product Reality test **before pressing Review & Promote Timing**:

1. Open Arrangement Preview.
2. Confirm candidate score notes are visible against the recording clock.
3. Inspect the first common entrance, expected near ~7.109 s rather than the previous ~11.773 s failure.
4. Inspect the later Lead landmark around ~77.756 s.
5. Scrub later in the song for drift.
6. Only if those checks are correct, use `Review & Promote Timing` and continue downstream arrangement construction.

Related: #480, #431, #455, #457, #193.