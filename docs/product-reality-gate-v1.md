# Product Reality Gate v1

The Product Reality Gate is a real-user evidence check for the packaged Windows application. It complements deterministic tests and CI; it does not replace them.

The gate asks whether a normal user can take one lawful song plus one complete structured score through the actual desktop workflow efficiently and understandably enough that the product is genuinely useful.

## Automation-first boundary

Product Reality is **not** permission to use the user as a repetitive test harness.

The project now follows this rule:

> **Zero humans for facts a computer can measure.**

A deterministic fact discovered during a human Product Reality session should become an automated regression or private local scenario before the same fact is requested from the human again. The Windows laptop may remain necessary because lawful private/commercial source material lives there, but the laptop should act as an unattended private test worker whenever the acceptance question is machine-measurable.

The automation order is:

1. repository unit/integration/golden tests for algorithms, transforms, import/export semantics, and validation;
2. Windows CI/desktop automation for packaging, startup, and deterministic desktop behavior;
3. the **Private Local Product Reality Runner** (`docs/private-product-reality-runner-v1.md`, issue #612) for deterministic correctness that requires private local song/score projects;
4. explicit human Product Reality only for irreducibly subjective or external-runtime judgments that automation cannot yet prove.

Human Product Reality remains appropriate for actual Rocksmith gameplay feel, tone preference, genuinely ambiguous fingering/playability judgment, final UX preference, and owner-only publication/licensing/copyright decisions. It should not be used to repeatedly measure timestamps, phase displacement, drift, shared-transform identity, stale authority, file/provenance identity, or other facts that the runner can calculate.

A change must not request a manual laptop retest when an existing automated lane can answer the same question. When no automated lane exists for a repeated deterministic check, creating that lane is test-debt work, not optional polish.

## Recorder purpose

The desktop **Product Reality Gate Recorder** records evidence while a real session is being performed. It deliberately lives outside the Song Workspace authoring inheritance chain and creates no musical authority.

The recorder captures:

- packaged build or artifact identifier supplied by the tester;
- registered recording SHA-256 and duration;
- registered score SHA-256/format when a score exists;
- manually started/stopped workflow stage timings;
- which stage intervals count toward human editing time;
- Bass/Lead/Rhythm correction counts for timing, position, technique, chord fingering, chord identity, and other corrections;
- usability/performance observations with `note`, `friction`, or `blocker` severity;
- whether an observation required CLI or PowerShell as a workaround;
- an explicit final Product Reality **PASS** or **FAIL** plus the reason.

While a stage timer is running, the recorder updates the active-stage elapsed time and live measured/editing totals once per second. These live values are presentation-only projections: they do not append a stage record or alter the active-session evidence. A stage contributes to persisted evidence only when **Stop Stage** records its completed interval.

The principal productivity metric is computed directly from measured stage time:

`editing minutes per finished minute = measured editing seconds / recording duration seconds`

The recorder never estimates editing time after the session. Final JSON/Markdown reports use stopped, persisted stage intervals only.

The recorder is therefore primarily for human-only UX/productivity evidence and genuinely subjective acceptance. Deterministic private-song assertions should migrate to the Private Local Product Reality Runner instead of being re-measured manually in every session.

## PASS evidence floor

A Product Reality **PASS** is fail-closed. The recorder refuses to finalize PASS unless the session contains the minimum evidence needed to support that claim:

- a packaged build/artifact identifier;
- a currently registered complete-score identity;
- at least one completed workflow stage interval with strictly positive elapsed time;
- at least one strictly positive measured interval explicitly marked as human editing time;
- at least one usability/responsiveness observation;
- no observation showing that the normal path required a CLI/PowerShell workaround;
- no unresolved observation marked as a blocker.

The registered score identity is refreshed from the current project state immediately before final gate evaluation. A session may therefore begin before score intake, and a score replaced during the run cannot leave stale provenance in the final evidence. If no score is registered at completion time, PASS remains blocked.

Zero-second timer records remain legal diagnostic records but do not satisfy either the completed-stage or measured-editing evidence requirement.

This is deliberately a baseline evidence floor, not a claim that one stage or one observation fully satisfies the complete operator checklist. The real v1 run should still exercise the full workflow areas listed below and record representative stage timings, correction counts, and responsiveness observations.

An incomplete or blocked session may always be finalized as **FAIL** with an explicit reason. Missing evidence must never force the tester to fabricate measurements merely to close the session.

## Local report files

An active session is stored beneath:

`diagnostics/product-reality/active-session.json`

Finishing the gate writes both JSON evidence and a human-readable Markdown summary beneath the same local diagnostics directory, then removes the active-session file.

These files are local/private project evidence and are gitignored. Do not commit private song/project reports, commercial media, CFSM exports, Ubisoft-derived data, or PSARC packages.

The Private Local Product Reality Runner uses its own append-only evidence records beside the private scenario by default; those records are likewise private/local and must not be committed merely to prove a commercial-song case.

## Workflow

1. Run all applicable deterministic repository/Windows/private-runner acceptance first.
2. If those lanes already answer the acceptance question, do **not** ask the user to repeat the same measurement manually.
3. Only when genuine human evidence remains, build or download the packaged Windows application being evaluated.
4. Open the lawful development project in the desktop application.
5. Open **Workspace → Product Reality Gate Recorder**.
6. Enter the packaged build/artifact identifier and start the session.
7. Start and stop stage timers as the real workflow progresses. Mark only genuine human correction/review intervals as editing time. The live display includes the currently running interval, while final evidence is committed only when that interval is stopped.
8. Increment correction counters when a real correction is required.
9. Record confusing states, responsiveness problems, workarounds, or blockers as they occur rather than reconstructing them afterward.
10. Finish the session with an explicit PASS or FAIL and a reason. PASS is accepted only when the baseline evidence floor above is satisfied; FAIL remains available for incomplete or blocked evidence runs.
11. Use the resulting report to create/prioritize focused GitHub issues and the next evidence-driven hardening work.
12. When a deterministic defect class is found, add automated protection so the same human measurement is not requested again.

## Gate expectations

Product Reality v1 should exercise, where current product scope permits:

- packaged-app launch and project open;
- recording/score intake and Bass/Lead/Rhythm mapping;
- shared timing review;
- synchronized arrangement preview and direct event selection;
- accepted timing, position, technique, chord/fingering, and chord-identity edits;
- undo/redo of accepted edits;
- validation/export/package handoff stages currently exposed by the desktop path;
- responsiveness on representative full-length/dense material;
- whether hidden CLI/PowerShell repair steps are still required.

The human session should focus on what automation has not already established. Repeating automated deterministic checks manually is not additional confidence; it is redundant test debt.

A technically complete milestone may fail Product Reality. A failure is useful evidence and must not be redefined away after the session.

## Authority boundary

Product Reality evidence cannot approve source rights, score mapping, timing promotion, fingering, techniques, chord identity, tones, validation, package readiness, or installation. It cannot alter imported score/fan-out bytes, the live Rocksmith installation, or NoCableLauncher.

Live timer projections are read-only UI state and cannot create or change Product Reality evidence authority. The recorder is measurement infrastructure only.

The Private Local Product Reality Runner is also measurement infrastructure only: private scenario expectations are acceptance data, never song-specific correction logic or musical authority.
