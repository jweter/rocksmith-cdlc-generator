# Shared Timeline Guitar Drafting

## Product change

The shared score workflow now crosses the first major multi-arrangement boundary:

**one recording + one complete score -> one reviewed timeline -> Bass + Lead + Rhythm draft paths**

Lead and Rhythm no longer require their own score-to-recording alignment operation when they come from the current human-confirmed complete-score fan-out.

## User flow

After score mappings are explicitly confirmed and the score is fanned out, the authoritative Bass projection is aligned to the recording once. The user reviews that timing and promotes it:

```text
cdlc-shared-timeline promote PROJECT
```

The planner then exposes deterministic guitar construction:

```text
cdlc-build-shared-guitar PROJECT --instrument lead
cdlc-build-shared-guitar PROJECT --instrument rhythm
```

`cdlc-plan` shows these as Lead/Rhythm shared-timeline draft steps, and `cdlc-auto` may execute them because they make no new source-selection or alignment-acceptance decision.

## Timing inheritance

Both guitar arrangements consume `alignment_for_role()` from the reviewed project-level shared timeline. Their arrangement-specific views retain their own confirmed score track and fan-out source path while inheriting exactly the same:

- recording identity;
- score identity;
- piecewise timing anchors;
- timing regions;
- global offset;
- residual/confidence diagnostics.

No second `align-source` operation is introduced for Lead or Rhythm.

## Guitar safety boundaries

The existing guitar authoring rules remain unchanged:

- explicit six-string tuning is required;
- source string/fret positions are preserved, not invented;
- unresolved positions remain unresolved and block clean export;
- simultaneous positioned notes become deterministic chord shapes;
- source trust/review flags remain visible;
- low-confidence shared timing remains reviewable.

## Draft provenance

Each shared-timeline guitar build writes:

- `charts/lead_source.json` or `charts/rhythm_source.json`;
- `charts/lead_shared_timeline.json` or `charts/rhythm_shared_timeline.json`.

The sidecar binds the draft to the current recording SHA-256, score SHA-256, exact arrangement source content hash, confirmed source track, and generated chart hash. A later score fan-out/source rewrite or chart edit makes that draft non-current instead of silently appearing complete.

## Planner behavior

For projects with current human-confirmed Lead/Rhythm fan-out:

1. Bass/shared-score alignment happens once.
2. Shared timing requires one explicit human promotion.
3. Lead and Rhythm become automatic draft steps from that same timeline.
4. Bass reconciliation and arrangement-specific validation/review remain separate downstream responsibilities.

This is intentionally the bridge into the next milestone: three-arrangement reconciliation, mapping/playability validation, and export readiness rather than three independent alignment pipelines.
