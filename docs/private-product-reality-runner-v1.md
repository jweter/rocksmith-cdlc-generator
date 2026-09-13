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
- derived timing/validation measurements;
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

## Scenario contract

Private scenario configuration lives outside Git by default. A scenario identifies a local project and the assertions to evaluate, but does not alter generation behavior.

```json
{
  "schema_version": 1,
  "scenario_id": "private-shared-timing-01",
  "project_dir": "C:/private/path/project",
  "scenario_type": "shared_timing",
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
      "expected_audio_seconds": 77.8,
      "symbolic_source_seconds": 74.0
    }
  ]
}
```

The example values illustrate shape only. Song-specific private expectations stay in the user's local scenario file and MUST NOT be hard-coded into production algorithms.

## Evidence contract

Every run writes one machine-readable evidence record under a local private results directory.

Required identity:

- runner schema/version;
- generator commit/build identity;
- scenario ID and type;
- project/source hashes where available;
- alignment/tempo/arrangement authority hashes where available;
- execution timestamp.

Required status vocabulary:

- `PASS` — all required deterministic assertions pass;
- `FAIL` — one or more deterministic assertions are falsified;
- `REVIEW_REQUIRED` — evidence is missing, stale, ambiguous, or outside automation authority.

A missing/stale authority artifact MUST NOT be converted into PASS.

## Shared-timing v1 scenario

The first implemented scenario automates the repeated #431/#455 acceptance facts from already-generated local project artifacts.

It should evaluate:

1. `analysis/tempo_map.json` exists and contains a usable beat grid.
2. `analysis/alignment.json` exists and belongs to the current recording/source authority where hashes are available.
3. First playable Bass, Lead, and Rhythm events can be read from generated/reviewed arrangement artifacts.
4. Their spread is within the configured tolerance so all roles share one practical timing transform.
5. Their first entrance matches the private expected entrance within tolerance.
6. Configured later source-time checkpoints map through the current alignment and remain within tolerance.
7. Drift between early and later checkpoints stays within tolerance.
8. Existing validation evidence has no blocking timing failure.
9. Any stale/invalidation marker that makes the result non-authoritative forces `REVIEW_REQUIRED`.

## CLI direction

The intended headless interface is:

```powershell
cdlc product-reality run --scenario C:\private\rocksmith-tests\shared-timing.json
```

The command should:

1. load and validate private scenario configuration;
2. resolve exact project/build identity;
3. run the deterministic evaluator;
4. append a JSON evidence record locally;
5. print a compact report;
6. exit non-zero on `FAIL`, and with a distinct non-zero code on `REVIEW_REQUIRED`;
7. never upload private source material.

A later launcher/UI action may call the same engine. The CLI remains the deterministic authority.

## Output shape

```text
PRODUCT REALITY — shared timing
Build: <commit/build>
Scenario: <private scenario id>

Audio beat grid:       PASS
Bass first event:      PASS  delta=<...>
Lead first event:      PASS  delta=<...>
Rhythm first event:    PASS  delta=<...>
Shared transform:      PASS
Later checkpoints:     PASS
Cumulative drift:      PASS
Stale authority:       NONE
Blocking validation:   0

RESULT: PASS
```

The JSON evidence contains the same measurements plus provenance hashes so successive runs can be diffed without reopening private media.

## Implementation slices

### Slice 1 — runner core

- typed scenario schema;
- typed evidence/result schema;
- shared-timing evaluator using existing project artifacts;
- local append-only-ish result history (new record per run, never overwrite prior result by default);
- synthetic tests for PASS, FAIL, REVIEW_REQUIRED, repeated-riff/two-measure regression shape, and stale authority.

### Slice 2 — Windows one-click execution

- launcher entry to run configured private scenarios unattended;
- readable summary after completion;
- no GUI navigation required.

### Slice 3 — broader deterministic Product Reality

- XML structural acceptance;
- PSARC staging/registration verification;
- Official TAB orientation/persistence automation where UI tooling permits;
- printed-score recognition completeness metrics;
- deterministic Arrangement Preview clock diagnostics.

### Slice 4 — external/game automation

Investigate safe automation for launching a staging copy into Rocksmith 2014, confirming package discovery/load, and collecting non-subjective smoke evidence without modifying official DLC/profile data.

## Human-only debt report

Every runner session should end with a concise list of what still genuinely needs a person. Example:

```text
Human-only acceptance debt:
- Play one representative section in Rocksmith and judge gameplay feel.
- Judge tone match.
```

If the list is empty, the user should not be asked to open the laptop test workflow.

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
