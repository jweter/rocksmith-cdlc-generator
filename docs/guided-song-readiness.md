# Guided song readiness

The primary desktop product now translates the internal workflow plan into a user-facing **Song readiness** surface. The goal is to make the normal authoring path answer three questions immediately:

1. How far through the current song is the workflow?
2. Does the application need a human decision, or can it continue automatically?
3. What is the next meaningful action in plain language?

## Product behavior

Both the packaged Windows application and the `cdlc-desktop` entry point launch `GuidedDesktopApp`, a thin composition layer over the existing `ProductDesktopApp`.

The guided layer shows:

- a readiness percentage based only on required workflow steps;
- a prominent `Needs you` state when an explicit human gate blocks progress;
- a plain-language next action such as confirming Bass/Lead/Rhythm score tracks or reviewing shared song timing;
- `Continue Automatically` when deterministic work can proceed without a musical/source-acceptance decision;
- a direct **Open Song Review** action into the existing Song Workspace.

Optional workflow helpers do not reduce the readiness percentage. Advanced workflow details, provenance state, logs, XML export, DLC Builder handoff, and other diagnostic/power-user surfaces remain available underneath the guided product layer.

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

This is the first convergence slice toward the intended normal workflow:

`recording + complete score → automatic setup → only necessary human review → build Rocksmith song`

Future slices should make the readiness actions increasingly direct (jump to the exact review/control needed) and eventually provide one validation-gated **Build Rocksmith Song** action, while keeping the current advanced tools available for diagnosis and power users.
