# Unattended Verification Policy

Routine engineering verification is machine-owned. Jeremy is not a recurring test executor and must not be placed inside ordinary implementation, regression, packaging, Product Reality, or promotion loops when objective evidence can be automated or collected by an unattended worker.

## Default verification path

`change -> FAST_GATE -> exact-head preflight -> CI -> unattended Windows/Product Reality verification -> structured evidence -> automated diagnosis/repair -> re-verification -> promotion -> optional Jeremy milestone acceptance`

Environment dependence is not automatically human dependence. Windows packaging, launcher-safe checks, generated-workspace inspection, local tooling, timing/alignment measurement, and other non-CI checks should first be scheduled to the approved unattended Rocksmith worker on an idle machine.

## Evidence classification

Use this order:

1. Repository-native deterministic test.
2. Unattended Windows/environment test.
3. Automatable Product Reality probe using logs, timing metrics, generated XML/workspace inspection, screenshots, artifacts, launch/import results, or machine-readable observations.
4. Human judgment only when the remaining question is genuinely subjective, ambiguous, irreversible, safety-sensitive, or a musical/product-direction decision.

`Jeremy must run this manually` is a workflow deficiency unless category 4 actually applies.

## Worker contract

An unattended worker must identify repository, branch, exact SHA, request, environment, and timestamp; record bounded commands/actions and evidence; return `PASS`, `FAIL`, `REVIEW_REQUIRED`, `PRODUCT_REALITY_REQUIRED`, or `ENVIRONMENT_FAILURE`; write permitted results back to the issue/PR/evidence ledger; fail closed on missing evidence; and leave the machine safe.

The worker must never modify live Rocksmith or NoCableLauncher, and must never commit or upload commercial audio, DLC, Ubisoft-derived restricted material, private score images, private/generated workspaces, credentials, or unrelated personal files. Sensitive/local paths should be redacted from diagnostics when practical.

Pending worker verification blocks only the dependent lane. EOF parity/reuse, deterministic validation, regression protection, UI/UX hardening, provenance-safe tooling, and Bass/Lead/Rhythm architecture continue when independent.

## Rocksmith application

Objective checks such as packaged-app startup, CLI/GUI launch, generated arrangement structural validation, Bass/Lead/Rhythm presence, count/end/section parity, timing offsets, click-track alignment, deterministic workspace outputs, crash detection, lock recovery, and reproducible import/build behavior should move into the unattended worker or CI.

Human review remains appropriate for irreducibly subjective musical feel, tone preference, fingering quality, ambiguous score interpretation, or source/provenance judgments that objective evidence cannot resolve. Even then, the system should automate all surrounding setup and evidence collection so Jeremy evaluates only the final subjective question.

Jeremy may always play a milestone or new version, but repeated incremental tests should not be required for development to continue.
