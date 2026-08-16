# Guided song readiness

The primary desktop product translates the internal workflow plan into a user-facing **Song readiness** surface. The normal authoring path should answer three questions immediately:

1. How far through the current song is the deterministic authoring workflow?
2. Does the application need a human decision now, or can it continue automatically?
3. What is the next meaningful action in plain language?

## Product behavior

Both the packaged Windows application and the `cdlc-desktop` entry point launch `GuidedDesktopApp`, a thin composition layer over the existing `ProductDesktopApp`.

The guided layer shows:

- a readiness percentage based only on required workflow steps;
- a prominent `Needs you` state only when the **currently actionable** workflow step requires human judgment;
- a plain-language next action such as confirming Bass/Lead/Rhythm score tracks or reviewing shared song timing;
- `Continue Automatically` when the earliest unresolved required step is deterministic work that can run safely;
- a direct **Open Song Review** action into the existing Song Workspace.

Later blocked human steps are dependencies, not premature requests to the user. For example, a future review queue must not produce `Needs you` while audio normalization is the actual next runnable action.

Optional workflow helpers do not reduce the readiness percentage. The planner's terminal `human-review` step is intentionally different: once validation has produced that review queue it remains an explicit human action, but it counts as prepared progress because there is no persistable `complete` state for that planner step. A project can therefore show **100% prepared** while still truthfully saying **Needs you: review the generated song draft**. The percentage is progress, not approval.

Advanced workflow details, provenance state, logs, XML export, DLC Builder handoff, and other diagnostic/power-user surfaces remain available underneath the guided product layer.

## Authority boundary

Song readiness is presentation only. It does not approve or infer:

- rights/provenance;
- score-track mappings;
- timing acceptance;
- notes, positions, fingering, techniques, chords, or tones;
- validation or package readiness;
- PSARC integrity or installation safety.

It derives its state from the existing authoritative `ProjectWorkflowPlan` and therefore cannot turn confidence, progress, or a percentage into authority.

## Product direction

This is the convergence path toward the intended normal workflow:

`recording + complete score → automatic setup → only necessary human review → build Rocksmith song`

The next usability slices should make the current readiness action direct: clicking it should jump to the exact review/control needed. After those guided review actions are coherent, the product can add one validation-gated **Build Rocksmith Song** path while keeping the current advanced tools available for diagnosis and power users.
