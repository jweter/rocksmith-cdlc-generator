# Shared guitar timeline transaction

Lead and Rhythm chart generation depends on the human-reviewed shared timeline and the current human-confirmed score mappings/fan-out outputs.

## Correctness boundary

`build_project_shared_guitar_chart()` holds the same project score transaction lock used by score remapping, score fan-out, and shared-timeline promotion for the complete shared-guitar build. The lock covers:

- loading and validating the current shared timeline;
- materializing the arrangement-specific alignment;
- loading the current arrangement fan-out source;
- applying reviewed position, event-timing, technique, and chord layers;
- building and writing the authoring chart;
- invalidating downstream validation/export/package derivatives; and
- hashing and publishing the shared-guitar draft manifest.

This prevents a shared timeline from being re-promoted between alignment materialization and manifest publication. Without this serialization, a chart built from timing transform A could theoretically be labeled with the hash of transform B.

A promotion that starts while a Lead/Rhythm build is active waits for the build transaction to complete. When the promotion subsequently publishes a new shared timeline, the previously completed guitar draft becomes stale normally because its stored `shared_timeline_sha256` no longer matches current authority.

## Human and safety boundaries

The transaction does not auto-accept timing, mappings, positions, techniques, chord identity, tones, or source rights. Existing human confirmation gates remain authoritative. The change does not write to the live Rocksmith installation or NoCableLauncher, and it does not add or redistribute commercial audio, DLC, private CFSM exports, or Ubisoft-derived content.
