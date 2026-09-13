# Private Local Product Reality Runner v1

Issue: #612

## Purpose

Routine Product Reality must stop requiring repeated human laptop sessions. The Windows laptop remains the lawful private execution environment for commercial/private song material, but deterministic acceptance should run unattended.

The rule is simple:

> **Zero humans for facts a computer can measure.**

Human review remains only where Rocksmith gameplay, musical feel, tone, subjective fingering, final UX, or publication/copyright judgment genuinely requires it.

## Boundary

The runner is local/private by design.

It MUST NOT commit, upload, or expose:

- commercial recordings or stems;
- private Guitar Pro, MusicXML, TAB, score images, or score books;
- generated private PSARC/CDLC packages;
- Steam profile/save data;
- private project workspaces;
- source bytes merely to make CI reproduce a Product Reality case.

It MAY persist locally:

- exact generator commit/build identity;
- scenario ID;
- content hashes of private inputs and authority artifacts;
- derived timing measurements;
- PASS / FAIL / REVIEW_REQUIRED results;
- human-only acceptance debt;
- timestamps and runner version.

Repository-safe synthetic fixtures may be committed to test runner semantics.

## Human-testing retirement policy

Testing categories retire from human execution as automated evidence becomes available:

| Category | Required evidence | Human needed? |
|---|---|---:|
| Algorithms, transforms, import/export semantics, validation | unit/integration/golden tests | No |
| Windows packaging/startup/deterministic desktop flows | Windows CI/automation | No |
| Private-song deterministic correctness | Private Local Product Reality Runner | No |
| Actual Rocksmith loading/playback | local automated smoke where practical; human only until automation exists | Sometimes |
| Gameplay feel, tone preference, ambiguous musical comfort | explicit human Product Reality | Yes |

A change must not ask for a manual laptop retest when an existing automated lane can answer the same question.

When a human Product Reality session discovers a deterministic defect, that defect class should be automated before the same fact is requested from the human again. Jeremy is not the test harness.

## Scenario contract

Private scenario configuration lives outside Git by default, preferably under an already ignored `private/` location or another private local directory. A scenario identifies a local project and assertions to evaluate; it does not alter generation behavior.

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

The example values illustrate shape only. Song-specific private expectations stay in the user's local scenario file and MUST NOT be hard-coded into production algorithms.

## Evidence contract

Every run writes one new machine-readable evidence record under a local private results directory. Existing evidence is never overwritten by default.

Required identity:

- runner schema/version;
- generator version and exact commit/build identity when available;
- scenario ID/type and scenario-file SHA-256;
- project recording SHA-256 where available;
- authoritative tempo-map SHA-256 where available;
- per-arrangement recording/score/source-output hashes;
- per-arrangement hash of the promoted reviewed timing points;
- execution timestamp.

Required status vocabulary:

- `PASS` — all required deterministic assertions pass;
- `FAIL` — one or more deterministic assertions are falsified;
- `REVIEW_REQUIRED` — evidence is missing, stale, ambiguous, or cannot be bound to an exact build.

A missing/stale authority artifact MUST NOT be converted into PASS.

## Shared-timing v1 implementation

The first implemented scenario automates the repeated #431/#455 timing facts from current promoted reviewed project authority.

The runner currently evaluates:

1. the authoritative audio tempo/beat map exists and contains at least two beats;
2. the running build can be bound to an exact commit SHA;
3. each requested Bass/Lead/Rhythm role can be materialized from **current promoted reviewed timing authority**;
4. each role's first playable event matches the private expected recording entrance within tolerance;
5. first-event spread across requested arrangements stays within tolerance;
6. requested arrangements share the same recording hash, score hash, and promoted reviewed timing-point transform;
7. configured later source-time checkpoints map to the expected recording time within tolerance;
8. checkpoint timing error does not drift materially from the first-event timing error;
9. missing/stale reviewed authority becomes `REVIEW_REQUIRED` rather than a guessed PASS.

The evaluator reads `reviewed_export_arrangement()` / `reviewed_arrangement_timing()` rather than trusting stale chart files. Existing repository currentness/provenance gates therefore remain authoritative.

Validation-report and PSARC/game smoke expansion are later slices; they are not falsely claimed as v1 coverage.

## CLI

The implemented headless interface is:

```powershell
cdlc-product-reality --scenario C:\private\rocksmith-tests\shared-timing.json
```

Optional result-location override:

```powershell
cdlc-product-reality --scenario C:\private\rocksmith-tests\shared-timing.json --results-dir C:\private\rocksmith-tests\results
```

Default evidence location:

```text
<scenario directory>/results/<scenario-id>/<timestamp>-<build-sha>.json
```

Exit codes:

- `0` = deterministic PASS;
- `2` = deterministic FAIL;
- `3` = REVIEW_REQUIRED / insufficient or stale evidence.

The command never uploads private source material.

## Output shape

```text
PRODUCT REALITY — shared timing
Build: <commit/build>
Scenario: <private scenario id>

build_identity                   PASS            ...
audio_beat_grid                  PASS            ...
bass_first_event                 PASS            ...
lead_first_event                 PASS            ...
rhythm_first_event               PASS            ...
arrangement_first_event_spread   PASS            ...
shared_timing_transform          PASS            ...
checkpoint_later-structure-1     PASS            ...
checkpoint_later-structure-1_drift PASS          ...

RESULT: PASS

Human-only acceptance debt:
- Judge final Rocksmith gameplay feel.
```

The JSON evidence contains the same measurements plus provenance hashes so successive runs can be diffed without reopening private media.

## Regression protection

`tests/test_private_product_reality.py` includes a synthetic reproduction of the #431/#455 failure class: all arrangements are shifted approximately 4.64 seconds / about two measures late, and a later checkpoint carries the same displacement. The runner must mark that scenario `FAIL` automatically. A human should never need to rediscover that class of error.

The tests also cover:

- normal shared-timing PASS;
- missing/unbound evidence -> `REVIEW_REQUIRED`;
- arrangements carrying different timing transforms -> `FAIL`;
- private scenario-relative project paths;
- append-only evidence history behavior.

## Implementation slices

### Slice 1 — runner core — implemented in this change

- typed private scenario schema;
- typed observation/evidence/check schemas;
- current reviewed-authority collector;
- shared-timing evaluator;
- exact build identity binding;
- local append-only evidence records;
- compact human-readable report;
- distinct PASS / FAIL / REVIEW_REQUIRED exit codes;
- synthetic regression coverage including the two-measure-late defect class.

### Slice 2 — Windows one-click execution

- launcher entry to run configured private scenarios unattended;
- optionally run safe automatic generation first, then the same deterministic evaluator;
- readable summary after completion;
- no GUI navigation required.

### Slice 3 — broader deterministic Product Reality

- validation/XML structural acceptance;
- PSARC staging/registration verification;
- Official TAB orientation/persistence automation where UI tooling permits;
- printed-score recognition completeness metrics;
- deterministic Arrangement Preview clock diagnostics.

### Slice 4 — external/game automation

Investigate safe automation for launching a staging copy into Rocksmith 2014, confirming package discovery/load, and collecting non-subjective smoke evidence without modifying official DLC/profile data.

## Human-only debt report

Every runner session ends with a concise list of what still genuinely needs a person. If that list is empty, the user should not be asked to open the laptop test workflow.

## Success condition

The normal development loop becomes:

```text
implementation
  -> automated repository tests
  -> Windows CI/package automation
  -> unattended private Product Reality runner
  -> machine PASS/FAIL evidence
  -> human only for irreducibly subjective/final gates
```

This is a product requirement, not optional test tooling. Repeated manual verification of deterministic facts is considered test debt to automate away.
