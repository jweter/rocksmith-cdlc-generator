# Synthetic-only CPU/RAM probe for controlled future Bass model pilots

Status: first bounded telemetry slice, **no external model or media execution**.
Tracking: #787, #612; staged before choosing any licensed separator.

## Why

Azathoth is a Windows 11 Home laptop with approximately 15.7 GiB total RAM.
During the 2026-11-21 read-only check, available physical RAM fell from
~5.87 GiB to ~4.82 GiB while unrelated workloads were active. That is below
the existing 7 GiB threshold for heavy source separation. Windows Sandbox
was not available (feature status unknown/unsupported; executable absent).
An OS-isolated network boundary therefore **cannot currently be assumed**.

The previous separation adapter is opt-in and pinned, but an ordinary
subprocess timeout is not measurement of process peak memory, and model
filename SHA-256 does not prove model-license compatibility or prevent an
upstream library from contacting the network.

## Implemented now

`cdlc-synthetic-ram-probe` prints readiness by default (no subprocess).
With `--run-synthetic`, it launches **only fixed Python standard-library
code** that allocates 1–64 MiB and holds it for 200–3000 ms. There is no
user-supplied command/script, song path, model path, installer, data upload,
or network operation in the child.

The test runner:
- measures the **probe process's resident set** every 25 ms on Windows
  (PSAPI working set) or Linux (`/proc/PID/statm`);
- records peak observed process RSS, elapsed time, sample count, exit
  status and lowest measured *available physical* RAM;
- requires pre-admission available RAM and rechecks it during execution;
- stops the probe if RSS exceeds its configured 8–256 MiB limit, host
  available RAM falls below its floor, data collection fails, or the
  tightly bounded time window expires;
- attempts process-tree termination on limit/timeout; reports uncertain
  termination explicitly rather than pretending success;
- emits only aggregate diagnostics, without user paths, source audio,
  filenames, model weights or private score events.

**Important:** sampled RSS cannot capture every transient peak, GPU
usage, or subprocess child tree; it is an observation, **not** an
OS-enforced memory budget. This fixed synthetic workload does not create
OS-level network isolation. It cannot qualify a heavy model.

## Usage

Default read-only:
```powershell
cdlc-synthetic-ram-probe
```

Explicit short synthetic test:
```powershell
cdlc-synthetic-ram-probe --run-synthetic --allocation-mib 8 --limit-mib 128 --hold-ms 350
```

A successful report states `SYNTHETIC_ONLY_PASS`, never `MODEL_READY`
or `GAMEPLAY_PASS`.

## Real timeout regression proof (#799)

The synthetic probe can now accept an explicitly bounded
`--max-runtime-seconds 0.45` while its fixed, non-network child is asked
to hold 8 MiB for 2500 ms. On CI this must report `TIMEOUT`, terminate
and reap the child, and **never** report `SYNTHETIC_ONLY_PASS`.
Deadlines outside 0.25–10 seconds (including nonfinite values) are
rejected before child launch. Completed children are checked before
timeout classification to avoid marking normal CI scheduling delays
as a process timeout.

This verifies a fixed test child only, not real model process-tree
containment or a guarantee of OS-enforced resource budgets.

## Next gates

1. Inspect model family, license, exact model digest, supporting
   dependency manifest and CPU/DirectML compatibility.
2. Establish a genuinely enforced and independently tested network
   boundary usable on **Windows Home**, or run in an independently
   isolated approved environment. Do not treat the `HF_HUB_OFFLINE`
   hint as an enforcement mechanism.
3. Implement **whole-child-tree peak memory** and enforceable containment
   for third-party inference (e.g. bounded Windows Job Object), including
   cleanup on timeout/crash.
4. Test the *same copyrighted-safe synthetic WAV* against existing
   score/onset ground truth and collect source-stem clock/quality proof.
5. Only then consider opt-in model inference. The normal unattended
   scheduled worker must not load unverified heavy models.

Current acceptance deliberately remains **no model executed**.
