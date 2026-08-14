# Automatic first-draft runner

`cdlc-auto PROJECT` advances a Bass project through deterministic first-draft stages until the workflow reaches a human decision.

It is intentionally an executor for the existing `cdlc-plan` contract, not a second independent pipeline. After each completed stage it rebuilds the plan from project artifacts before deciding what may run next.

## Intended normal workflow

```text
local recording + optional tab/notation
        ↓
rights/provenance confirmation when needed
        ↓
cdlc-auto PROJECT
        ↓
normalize recording
        ↓
beat / variable-tempo analysis
        ↓
audio-derived Bass transcription
        ↓
align one unambiguous imported Bass tab to the recording
        ↓
reconcile tab parts with audio evidence
        ↓
map playable strings/frets
        ↓
run validation and create review queue
        ↓
STOP for human review
```

If multiple imported Bass sources or multiple Bass tracks are plausible, automation stops rather than choosing one silently. The user records that source/track decision through the existing alignment workflow, after which `cdlc-auto` can resume from the new project state.

## Safety properties

- Executes no `human` workflow step.
- Invokes no shell and accepts only a small whitelist of planner-owned deterministic `cdlc` commands.
- Never launches DLC Builder, installs a PSARC, edits the live Rocksmith installation, or touches NoCableLauncher.
- Never changes rights classifications or recording-version/source acceptance decisions.
- Rebuilds the workflow plan after every stage and stops if a successful command did not advance project state.
- Uses a bounded stage count (`--max-steps`, default 8) to prevent runaway execution.
- Treats Bass validation exit code `2` as a normal review outcome when the validation report contains blocking issues; the next state is the human review gate.

## Commands

```powershell
cdlc-plan "projects\artist-song"
cdlc-auto "projects\artist-song"
cdlc-auto "projects\artist-song" --max-steps 3
```

The JSON result includes every executed step, its return code, the stop reason, the next workflow step, and the final project plan. This is also intended as a future Windows Song Workspace orchestration contract: the GUI can start deterministic work automatically and then present the exact human review gate that stopped it.
