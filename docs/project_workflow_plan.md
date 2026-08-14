# Guided project workflow plan

`cdlc-plan PROJECT` is a read-only planning surface for the normal human workflow. It turns the current project artifacts and source inventory into an ordered JSON plan whose steps are explicitly marked as `automatic` or `human` and as `complete`, `ready`, `blocked`, or `optional`.

The purpose is to remove the requirement that a user already understand the Rocksmith authoring sequence before starting. The future Windows GUI can consume the same model to present one clear next action while still preserving human review gates.

## First-draft path

The current plan covers the Bass-first path through the review-ready draft:

1. recording audio available;
2. human source-rights/provenance confirmation where required;
3. optional recording/version reference selection and reviewed context;
4. deterministic audio normalization;
5. beat and variable-tempo analysis;
6. audio-derived Bass transcription;
7. tab/notation-to-recording alignment when one parsed symbolic source is available;
8. symbolic/audio reconciliation so disagreements become review flags;
9. playable Bass string/fret mapping;
10. unified validation;
11. human review of flagged timing, notes, fingering, and source disagreements.

A single parsed tab/notation source can proceed automatically into alignment once the tempo map exists. Multiple parsed symbolic sources remain a human source-acceptance decision because the engine must not silently decide which arrangement is authoritative.

## Example

```powershell
cdlc-plan "projects\artist-song"
```

The JSON includes `next_step_id`, counts of automatic-ready and human-blocking steps, and an executable command only for steps whose operation is deterministic. Human gates never receive an invented automatic approval.

## Safety boundaries

- Planning is read-only; it executes no pipeline command.
- It does not download, rip, probe, transcode, modify, install, or package media.
- It does not choose among ambiguous tabs/arrangements.
- It does not elevate generated or imported musical content to trusted ground truth.
- Rights/provenance, recording-version selection, uncertain musical correction, and final source acceptance remain human-reviewed.
- It never modifies the live Rocksmith installation or NoCableLauncher.

This planner is intentionally a shared engine/GUI contract. Later GUI work should render these states and commands rather than duplicating workflow policy in presentation code.
