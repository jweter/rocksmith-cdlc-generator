# Private Local Product Reality Runner v1

Issue: #612

## Purpose

Routine Product Reality must stop requiring repeated human laptop sessions. The Windows laptop remains the lawful private execution environment for commercial/private song material, but deterministic acceptance should run unattended.

> **Zero humans for facts a computer can measure.**

Human review remains only where Rocksmith gameplay, musical feel, tone, subjective fingering, final UX, or publication/copyright judgment genuinely requires it.

The concrete Windows/Ollama worker implementation is documented in `docs/unattended-local-worker-v1.md`.

## Privacy boundary

The runner is local/private by design. It MUST NOT commit, upload, or expose commercial recordings or stems; private Guitar Pro, MusicXML, TAB, score images, or score books; generated private PSARC/CDLC packages; Steam profile/save data; private project workspaces; or source bytes merely to make CI reproduce a Product Reality case.

It MAY persist locally exact generator commit/build identity, scenario ID, content hashes of private inputs and authority artifacts, derived timing/validation measurements, PASS / FAIL / REVIEW_REQUIRED results, human-only acceptance debt, timestamps, and runner version.

Repository-safe synthetic fixtures may be committed to test runner semantics.

## Human-testing retirement policy

| Category | Required evidence | Human needed? |
|---|---|---:|
| Algorithms, transforms, import/export semantics, validation | unit/integration/golden tests | No |
| Windows packaging/startup/deterministic desktop flows | Windows CI/automation | No |
| Private-song deterministic correctness | Private Local Product Reality Runner | No |
| Actual Rocksmith loading/playback | local automated smoke where practical; human only until automation exists | Sometimes |
| Gameplay feel, tone preference, ambiguous musical comfort | explicit human Product Reality | Yes |

A change must not ask for a manual laptop retest when an existing automated lane can answer the same question. When a human Product Reality session discovers a deterministic defect, that defect class must gain automated coverage before the same fact is requested from the human again.

## Scenario contract

Private scenario configuration lives outside Git by default. A scenario identifies a local project and assertions to evaluate; it does not alter generation behavior.

```json
{
  "schema_version": 1,
  "scenario_id": "private-shared-timing-01",
  "project_dir": "C:/private/path/project",
  "scenario_type": "shared_timing",
  "roles": ["bass", "lead", "rhythm"],
  "expected": {
    "first_playable_seconds": 7.13,
    "first_playable_tolerance_seconds": 0.20,
    "max_arrangement_spread_seconds": 0.05,
    "max_checkpoint_error_seconds": 0.20,
    "max_drift_seconds": 0.20
  },
  "checkpoints": [
    {
      "id": "later-structure-1",
      "role": "bass",
      "source_time_seconds": 74.0,
      "expected_audio_seconds": 77.8
    }
  ],
  "human_only_acceptance": [
    "Judge final Rocksmith gameplay feel."
  ]
}
```

The values above illustrate schema shape only. Song-specific private expectations stay in local scenario data and MUST NOT be hard-coded into production algorithms.

## Evidence contract

Every configured-scenario run writes a new machine-readable evidence record. Existing evidence is never overwritten by default.

Required identity includes runner schema/version, generator version and exact commit/build identity when available, scenario ID/type and scenario-file SHA-256, project recording SHA-256 where available, authoritative tempo-map SHA-256 where available, per-arrangement recording/score/source-output hashes, per-arrangement hash of promoted reviewed timing points, and execution timestamp.

Required status vocabulary:

- `PASS` — all required deterministic assertions pass;
- `FAIL` — one or more deterministic assertions are falsified;
- `REVIEW_REQUIRED` — evidence is missing, stale, ambiguous, or cannot be bound to an exact build.

Missing/stale authority MUST NOT be converted into PASS.

## Shared-timing v1 implementation

The first scenario automates the repeated #431/#455 timing facts from current promoted reviewed project authority. It evaluates:

1. the authoritative audio tempo/beat map exists and contains at least two beats;
2. the running build can be bound to an exact commit SHA;
3. each requested Bass/Lead/Rhythm role can be materialized from current promoted reviewed timing authority;
4. each role's first playable event matches the private expected recording entrance within tolerance;
5. first-event spread across requested arrangements stays within tolerance;
6. requested arrangements share the same recording hash, score hash, and promoted reviewed timing-point transform;
7. configured later source-time checkpoints map to expected recording time within tolerance;
8. checkpoint timing error does not drift materially from the first-event timing error;
9. missing/stale reviewed authority becomes `REVIEW_REQUIRED` rather than a guessed PASS.

The evaluator reads `reviewed_export_arrangement()` / `reviewed_arrangement_timing()` rather than trusting stale chart files.

The unattended worker adds a second zero-configuration timing-health lane for recent desktop projects: when a current shared timeline exists, it reruns the independent multi-event audio-vs-symbolic source-timing qualification. That gives the laptop a way to surface a large phase/translation mismatch without first requiring the user to author a private scenario.

## Commands

Direct private scenario:

```powershell
cdlc-product-reality --scenario C:\private\rocksmith-tests\shared-timing.json
```

Unattended worker engine:

```powershell
cdlc-local-worker
```

The packaged Windows executable also supports a private `--unattended-worker` mode used by Task Scheduler. Normal desktop launch registers/refreshes that task automatically; the user is not expected to run these commands for routine operation.

Configured scenario exit codes remain `0` PASS, `2` FAIL, and `3` REVIEW_REQUIRED. The scheduled unattended worker defaults to process exit 0 even when Product Reality finds a product failure; the product result is stored in its evidence instead of making Windows treat the scheduler itself as broken.

## Local unattended worker

Implemented by the current #612 Windows slice:

- normal packaged/source desktop launch silently registers or refreshes a current-user Windows Task Scheduler task;
- task runs after 10 minutes of Windows idle time;
- recent projects are discovered from the existing desktop settings, not from user re-entry;
- private scenarios are auto-discovered from local/gitignored roots;
- worker history and `latest.json` remain under local app data;
- overlapping runs are blocked by a local lock;
- deterministic timing checks remain Python authority;
- on FAIL/REVIEW_REQUIRED, local Ollama may provide a schema-validated advisory diagnosis from sanitized derived measurements only;
- Ollama is loopback-only and cannot change deterministic PASS/FAIL status;
- the Ollama prompt explicitly treats routine debugging/reruns/log reading as automation work rather than a reason to involve the user.

See `docs/unattended-local-worker-v1.md` for the full implementation and safety contract.

## Regression protection

`tests/test_private_product_reality.py` includes a synthetic reproduction of the #431/#455 failure class: all arrangements are shifted approximately 4.64 seconds / about two measures late, and a later checkpoint carries the same displacement. That scenario must fail automatically.

`tests/test_unattended_worker.py` adds coverage for local-only Ollama enforcement, sanitized diagnosis payloads, private-scenario discovery, advisory-only LLM authority, idle/no-work behavior, and silent Windows idle-task registration.

## Implementation slices

### Slice 1 — runner core — implemented

- typed private scenario/evidence contracts;
- current reviewed-authority collector;
- shared-timing evaluator;
- exact build binding;
- local evidence history;
- PASS / FAIL / REVIEW_REQUIRED semantics;
- synthetic two-measure-late regression coverage.

### Slice 2 — unattended Windows execution — implemented

- packaged hidden worker mode and source CLI;
- automatic Windows idle-task registration/refresh;
- auto-discovery of local scenarios;
- zero-configuration recent-project timing qualification;
- local `latest.json` + history;
- local Ollama advisory diagnosis on failures;
- no GUI navigation required.

### Slice 3 — broader deterministic Product Reality — next

- validation/XML structural acceptance — implemented (PR #622);
- PSARC staging/registration verification — `verify_psarc_registration()` / `cdlc verify-psarc-registration PROJECT` re-checks a previously written `psarc_receipt.json` against current on-disk state (staged PSARC hash/header, build readiness manifest, DLC Builder project, and every registered input asset) without mutating anything, so drift after registration (edited XML/audio, a moved or rebuilt PSARC, a stale receipt) is a deterministic FAIL rather than silent trust; now wired into `run_private_product_reality()`'s automated evidence collection — `collect_shared_timing_observation()` calls it for every scenario's project directory and folds the result into a `psarc_registration` check (PASS/FAIL) alongside the shared-timing checks; a project that has never been registered (no receipt yet) is left unchecked rather than failed, since packaging is a later stage than shared-timing acceptance; an unreadable/corrupt receipt is reported as a `REVIEW_REQUIRED` collection error instead of crashing the scenario;
- Official TAB orientation/persistence automation where UI tooling permits;
- printed-score recognition completeness metrics;
- deterministic Arrangement Preview clock diagnostics.

### Slice 4 — external/game automation — later

Investigate safe automation for launching a staging copy into Rocksmith 2014, confirming package discovery/load, and collecting non-subjective smoke evidence without modifying official DLC/profile data.

## Human-only debt report

Every runner session should expose only what still genuinely needs a person. If that list is empty, the user should not be asked to open the laptop test workflow.

## Success condition

```text
implementation
  -> automated repository tests
  -> Windows CI/package automation
  -> unattended private Product Reality worker
  -> machine PASS/FAIL evidence
  -> local Ollama diagnosis where useful
  -> human only for irreducibly subjective/final gates
```

Repeated manual verification of deterministic facts is considered test debt to automate away.
