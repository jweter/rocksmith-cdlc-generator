# Windows Job Object containment — fixed synthetic resource probe (slice #09)

This implementation uses the Windows kernel **Job Object** API for the fixed,
Python-stdlib-only synthetic resource probe. The installed Rocksmith program,
NoCableLauncher, owned Ollama runtime, Steam libraries and private music
remain untouched. No actual source-separation model runs in this slice.

## The old gap

Sampling one child's RSS and calling `taskkill /T` after a threshold is a
best-effort diagnostic. A subprocess could fork a descendant, exceed its
budget between samples, or exit before the cleanup loop noticed. That is not
an OS-enforced resource boundary.

## New Windows-only execution sequence

1. Allocate a fresh Job Object, apply
   `JOB_OBJECT_LIMIT_JOB_MEMORY | JOB_OBJECT_LIMIT_ACTIVE_PROCESS |
   JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`.
2. Set the fixed user-facing synthetic probe's total job committed-memory
   bound to the configured 8–256 MiB and active process cap to 3.
3. Create the short-lived Python child with **CREATE_SUSPENDED** and no
   visible console. Attach its process to the configured job **before**
   resuming its primary thread; if any API fails, terminate the suspended
   child without executing Python model/workload code.
4. Keep sampling observed per-process RSS and host available physical RAM.
   A Windows Job Object supplies an independent **OS-enforced aggregate job
   commit cap**, which includes children by inheritance. The report adds
   `os_process_tree_memory_limit_enforced` and
   `peak_job_commit_mib` (queried through
   `JobObjectExtendedLimitInformation.PeakJobMemoryUsed`).
5. On success, timeout, memory sensor failure or process error, close the
   Job Object handle. The `KILL_ON_JOB_CLOSE` rule kills surviving
   descendants even if the direct child already exited.

This is **not an OS sandbox for networking**, and Windows Sandbox is not
assumed available on Azathoth's Windows 11 Home edition. A Job Object is
not a GPU VRAM budget, and committed-memory peak is different from
sampled physical resident RAM. Reports explicitly keep
`gpu_memory_measured=false` and `network_isolation_proven=false`.

Linux uses the previous local synthetic process-group monitor; no Windows
Job Object/OS-enforced memory cap is claimed for Linux.

## Exact tests

A Windows CI job must start the fixed child **in the job**, confirm an
OS aggregate commit memory peak, fail a deliberately over-budget allocation,
and prove a spawned grandchild is terminated when its parent job is
terminated/closed. Cross-platform tests continue to verify no spawn in
readiness-only mode, host RAM floor, timeout, synthetic RSS limit,
sensor failure and private report hygiene.

The implementation does not accept an arbitrary executable from the
CLI: `cdlc-synthetic-ram-probe --run-synthetic` continues to spawn only
its original fixed short memory fixture.

## Boundaries and next prerequisites

- **Proved by a green Windows CI run only:** kernel job assignment before
  resume, resource limit, and child-tree cleanup on a synthetic workload.
- **Not proved:** available RAM for a real separator (Azathoth was below
  the preexisting 7 GiB admission floor), the model's license/cache
  dependency closure, child-tree GPU usage, network isolation, stem
  separation purity, accurate Bass notes, or Rocksmith gameplay.
- Next, separately validate a Windows Home-compatible **network-denial**
  boundary and one explicit-rights-pinned cached provider before connecting
  this containment strategy to actual third-party inference.

Tracking: #796 slice 09; #787 and #612 remain parent goals.
