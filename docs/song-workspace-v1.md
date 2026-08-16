# Song Workspace v1

Song Workspace is the primary project-facing authoring surface in the Windows desktop application.

## What v1 provides

- one persistent window centered on the currently open song project;
- project-health and workflow-completion summary;
- the current next-best workflow action;
- recording and complete-score provenance status;
- Bass, Lead, and Rhythm status visible together;
- confirmed score-track mapping status per arrangement;
- draft-currentness, validation status, flag counts, and Rocksmith XML readiness per arrangement;
- a combined Bass/Lead/Rhythm review queue sorted by priority and time;
- direct navigation from a review item to its position on the visual timeline;
- detected beat markers, reviewed shared-timeline anchors, review markers, and a click-position review cursor;
- a read-only project snapshot model so opening/refreshing the workspace cannot implicitly accept a human decision;
- direct access from the packaged Windows desktop shell.

Source provenance badges are read from the same `ProjectSourceInventory` authority used by workflow gates. The workspace therefore treats explicit accepted intake classification as resolved when the inventory does, and it stays fail-closed when duplicate receipts for the same immutable source still require review or carry a conflicting effective rights state. Complete-score provenance is additionally route-specific: the score badge is reviewed only when a matching `register_score_source` inventory receipt exists and is resolved, matching the workflow and score-fanout authority gates. The workspace does not infer acceptance from the presence of a file or from a historical review receipt alone.

## Why this milestone matters

The project already has substantial engine capability. Song Workspace turns that capability into a product a person can understand while working on a real song. Instead of navigating artifact files and CLI commands, the user can see where the project is, what is blocking it, which arrangement needs attention, and where review problems occur in song time.

The timeline in v1 is intentionally a visualization and navigation foundation. It is not yet the full audio editor. The next workspace milestones add synchronized playback, waveform data, zoom/scroll/loop selection, beat-anchor editing, arrangement note/chord overlays, and fretboard interaction on top of this stable project-facing model.

## Authority boundaries

Viewing a project never changes authority. Song Workspace v1 does not:

- confirm score mappings;
- approve source rights/provenance;
- promote shared timing;
- clear review flags;
- invent string/fret positions;
- bypass validation or package-readiness gates.

Those actions remain explicit human or validation-controlled operations.

## Next desktop product milestones

1. Synchronized local audio playback and moving playhead.
2. Real waveform/overview data and timeline zoom/scroll.
3. Loop selection and slowed review playback.
4. Beat/downbeat and shared-anchor editing with reversible reviewed timing.
5. Bass/Lead/Rhythm note and chord overlays.
6. Unified issue navigation tied to playback and arrangement selection.
7. Virtual fretboard and fingering/chord editing.
8. Metadata, tone, export, DLC Builder, and PSARC readiness dashboards.
9. Installer/release workflow for normal Windows installation.

See `PROJECT_PLAN.md`, `docs/PRODUCT_VISION.md`, and `docs/windows-desktop.md` for the canonical direction.
