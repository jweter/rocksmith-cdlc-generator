# Unattended Local Worker v1

Issue: #612

## Product requirement

The Windows laptop is a private test worker, not a reason to make the user perform routine QA.

The governing rule remains:

> **Zero humans for facts a computer can measure.**

This worker turns the existing Private Local Product Reality Runner into unattended Windows behavior and adds local Ollama diagnosis without making the LLM a source of measurement authority.

## Activation

The packaged Windows application now registers a current-user Windows Task Scheduler task in the background when the GUI launches normally.

- task name: `Rocksmith CDLC Unattended Worker`;
- trigger: after 10 minutes of Windows idle time;
- no elevation or GUI interaction is intentionally requested;
- registration is idempotent;
- registration failure never blocks the desktop application and is retried on a later launch;
- `ROCKSMITH_CDLC_DISABLE_UNATTENDED_WORKER=1` disables registration for machines where background execution is not desired.
- A Windows Task Scheduler task that the owner has independently **disabled** is **never silently re-enabled** when the GUI launches. The packaged application checks the existing task's XML-enabled state before refreshing its command. Missing tasks can be created; **enabled** tasks can be refreshed to the current executable; an **unknown/malformed/inaccessible** task state is preserved and reported rather than force-overwritten.
- A disabled task with a stale executable path is a **blocked unattended workflow**. To resume deliberately, the owner must first authorize re-enabling the task, then launch the currently packaged Rocksmith app so the application can refresh the enabled task's executable path. Do not enable a deliberately disabled task as a side effect of unrelated code updates.

The packaged executable has a private `--unattended-worker` mode. Source/development installs can use `cdlc-local-worker` directly. The scheduled task runs the same deterministic worker engine rather than automating clicks through the GUI.

## What runs without the user

The worker has two evidence lanes.

### 1. Configured private Product Reality scenarios

The worker automatically discovers valid scenario JSON beneath these local-only locations:

- `%LOCALAPPDATA%/RocksmithCDLCGenerator/unattended-worker/scenarios/`;
- `<repo>/private/product-reality-scenarios/` when running from a source checkout;
- `<repo>/private/product-reality-inbox/` when running from a source checkout.

Those locations are private/local. The worker runs each scenario through the existing build-bound `cdlc-product-reality` engine and stores evidence under its private worker state directory.

### 2. Recent-project automatic timing health

A private scenario file is not required for the first automatic health lane.

The worker reads the desktop application's existing recent-project list from `%LOCALAPPDATA%/RocksmithCDLCGenerator/desktop.json`. For each recent project that has a current shared timing authority, it reruns the existing independent multi-event audio-vs-symbolic source timing qualification.

This is important for the historical two-measure timing failure: the check compares the shared symbolic timing projection against strong audio-derived Bass onset evidence and can identify a large repeated translation without asking a person to inspect timestamps.

Projects for which that check is not applicable are skipped rather than converted into false failures.

### 3. Optional auto-cdlc environment readiness monitoring

The existing idle worker can now include **read-only upstream model
readiness** evidence as a separate, explicitly enabled lane. Configure
local paths in the optional `worker.json` on the laptop:

```json
{
  "schema_version": 1,
  "auto_cdlc": {
    "enabled": true,
    "fixture_dir": "C:/MusicBench/fixture",
    "upstream_checkout": "C:/MusicBench/auto-cdlc-reviewed",
    "python_313_exe": "C:/MusicBench/venv/Scripts/python.exe",
    "run_parent": "C:/MusicBench"
  }
}
```

Paths are explicit and private. The idle worker does not discover
commercial music libraries or download any model. It calls the already
validated `cdlc-auto-cdlc-doctor`, then stores an **allow-listed
summary only** under `auto_cdlc_readiness` in its local `latest.json`
and history. The summary contains blocker codes, free physical RAM/disk
and package counts. It omits paths, input hashes, arbitrary exception
messages, track identities and model output bytes. The existing GitHub
public summary is **unchanged** and does not publish this local status.

The monitoring lane does **not** launch auto-cdlc, install Python or
dependency weights, or call Wwise. Its READY_TO_ATTEMPT_SYNTHETIC status
is strictly prerequisite readiness, not proof of transcription
accuracy, Bass/Lead/Rhythm Product Reality, PSARC or gameplay. BLOCKED
and UNAVAILABLE leave the worker's core Product Reality PASS/FAIL/IDLE
status untouched; missing optional third-party models never trigger
Ollama diagnoses or requests for human timestamp tests.
## Deterministic authority versus Ollama

Python remains the measuring instrument.

Deterministic code decides:

- whether private scenario checks PASS / FAIL / REVIEW_REQUIRED;
- whether the audio beat/timing evidence is current;
- first-event and checkpoint error where a private scenario defines those expectations;
- independent source timing qualification for applicable recent projects;
- build/provenance identity.

Ollama is advisory only.

When deterministic evidence returns `FAIL` or `REVIEW_REQUIRED`, the worker may send a sanitized derived-evidence object to local Ollama. The default model is `gemma3:4b`, matching the existing local environment. The request is refused unless the configured Ollama host resolves to loopback (`127.0.0.1`, `localhost`, or `::1`).

The Ollama payload contains no commercial audio, score image, GP/MusicXML bytes, private project path, PSARC, Steam data, or private source hash. It receives status/check text and derived timing measurements needed to classify the failure.

Ollama returns a schema-validated advisory diagnosis containing:

- defect category;
- evidence summary;
- cautious likely root cause;
- next **automated** action;
- whether a human is genuinely required;
- confidence.

An Ollama outage or malformed response never changes a deterministic PASS/FAIL result. It only means advisory diagnosis is unavailable for that run.

## Human boundary

The local model is explicitly instructed not to escalate ordinary engineering work to the user. Reruns, timestamp inspection, log reading, regression reproduction, deterministic debugging, stale-state analysis, and code fixes are machine/engineering tasks.

Human involvement remains valid for:

- actual guitar-in-hand gameplay feel;
- tone preference;
- genuinely ambiguous fingering/playability judgment;
- new product/creative direction;
- final UX preference when no objective criterion exists;
- publication/licensing/copyright authorization.

A deterministic failure should produce evidence for engineering, not another request that the user sit at the laptop and rediscover it.

## Local evidence

Default worker state:

```text
%LOCALAPPDATA%/RocksmithCDLCGenerator/unattended-worker/
  latest.json
  history/<timestamp>.json
  results/scenarios/<scenario-id>/...
  scenarios/...
```

`latest.json` is the current machine-readable status. `history/` retains time-stamped worker runs. Private Product Reality scenario evidence remains local.

When recent-project timing qualification has too few strong events, local evidence retains
the separate symbolic, total-audio, confidence, timing-confidence, pitch-confidence, and
joint strong-event counts. GitHub publication exposes only aggregate counts of affected
projects under allow-listed diagnostic codes. It never publishes per-project event counts,
song identity, paths, hashes, or raw diagnostic text, and it never weakens the qualification
thresholds to manufacture a timing result.

Worker top-level states:

- `PASS` — every applicable deterministic lane passed;
- `FAIL` — at least one deterministic assertion was falsified;
- `REVIEW_REQUIRED` — evidence is insufficient/stale/ambiguous;
- `IDLE` — no configured scenario and no applicable recent-project timing check exists;
- `BUSY` — another worker instance already owns the local lock.

A local lock prevents overlapping idle-triggered runs.

## Safety boundaries

The worker does **not**:

- modify the live Rocksmith installation or NoCableLauncher;
- upload private source media;
- turn Ollama output into musical authority;
- apply song-specific correction offsets;
- merge or push code;
- auto-approve source rights, fingering, tone, packaging, or publication;
- reinterpret missing evidence as PASS.

Its job is to observe, measure, diagnose, and leave durable local evidence so engineering can continue without using the user as the test harness.

## Current completion state

This change implements the #612 one-click/unattended Windows slice:

1. idle-triggered Windows worker registration from the packaged desktop entry point;
2. hidden packaged `--unattended-worker` execution mode;
3. `cdlc-local-worker` deterministic CLI;
4. automatic private-scenario discovery;
5. automatic recent-project source-timing qualification with no scenario authoring required;
6. local worker history/latest evidence;
7. loopback-only schema-validated Ollama failure diagnosis;
8. regression coverage for registration, privacy, idle behavior, and advisory-only LLM authority.

The next automation slices remain broader XML/PSARC structural acceptance, more deterministic GUI-state inspection, printed-score completeness diagnostics, and safe external Rocksmith smoke automation where feasible.
