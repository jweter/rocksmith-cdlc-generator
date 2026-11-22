# Child-tree RSS and GPU measurement transparency — synthetic proof (#796 slice 10)

## Scope and purpose

The short, fixed-code `cdlc-synthetic-ram-probe --run-synthetic` is our
resource-sensor proving ground. It is **not a model runtime** or a test of
private music. The previous probe measured only the direct child process
working set plus Windows kernel **aggregate Job Object peak committed bytes**.
Those figures are different: a grandchild can consume considerable resident
RAM without being counted in the direct child working set.

## Windows Job Object child-tree observation

On Windows only, `WindowsJobChild.current_tree_working_set_bytes` now uses
the kernel's `QueryInformationJobObject(JobObjectBasicProcessIdList)` to
enumerate **every active process assigned to the job**. Its PID list must
be complete and internally consistent; it never truncates excess items
into an apparently safe partial sum. It then calls
`OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ)` and
`GetProcessMemoryInfo` for every PID. The resulting total is the sampled
**sum of each process's working set (RSS)**, including short-lived
grandchildren when they are alive at the sampling point.

If PID enumeration or any process's working-set read fails, it reports
`JOB_TREE_SAMPLE_UNAVAILABLE` instead of assuming the missing process
used 0 MiB. The report adds:

- `peak_job_tree_rss_mib`: largest successfully sampled complete
  job-tree RSS sum, or `null` when not measured.
- `job_tree_rss_status`: `SAMPLED_COMPLETE_ACTIVE_JOB_PIDS` or
  `UNAVAILABLE_NO_COMPLETE_JOB_PID_SNAPSHOT`; Linux and other
  platforms report `UNAVAILABLE_NON_WINDOWS_NO_JOB_OBJECT`.
- Existing `peak_process_rss_mib`: *direct Python child* working set,
  separate from job-tree aggregate.
- Existing `peak_job_commit_mib`: OS Job Object's **peak committed
  bytes**, not summed physical RSS and not GPU VRAM. It can include
  a failed allocation's high-water observation, so compare enforced
  limits to the separate `JobMemoryLimit` readback.

Shared read-only process pages may appear more than once in summed RSS.
The timestamped sampling cadence can miss brief spikes; **kernel committed
memory cap** is the enforcement boundary, not sampled RSS.

## GPU usage

`peak_gpu_memory_mib=null`, `gpu_memory_measured=false`,
and `gpu_memory_status=UNAVAILABLE_NO_RELIABLE_PROCESS_GPU_COUNTER`
are deliberate. GPU VRAM must **not** be represented as 0 when unavailable,
inferred from CPU RAM, or conflated with the process working set.

Windows Performance Counters (WDDM GPU Process Memory) require a
driver-specific, validated attribution procedure. Microsoft's diagnostic
documentation identifies circumstances where the Dedicated GPU Memory
counter is missing or returns zero. Until that counter's provenance,
accuracy and child-PID attribution are independently validated, an
unavailable status is the scientifically defensible result. This slice
adds no VRAM limit and makes no acceleration claim.

## Testable acceptance

1. Real Windows CI runs an isolated, internally fixed short-lived Python
   parent which creates one child allocating 18 MiB; Windows Job Object
   reports at least two active PIDs and a sum of resident memory greater
   than the direct parent process RSS. A closed Job Object returns no
   plausible residual measurement.
2. Main synthetic probe must return positive aggregate job-tree memory on
   Windows; if the sensor is made unavailable while it is running,
   it fails closed rather than returning `SYNTHETIC_ONLY_PASS`.
3. Cross-platform regression keeps the GPU value `null` with an explicit
   unavailability reason and rejects false CPU/GPU resource claims.
4. The existing physical RAM floor, child-tree kernel committed-memory
   limit, timeout, owner privileges, media safety and zero-unapproved-
   model-execution controls remain unchanged.

This is a **synthetic observability milestone** only. It is not evidence
of available RAM on Azathoth, a real `audio-separator` model's resource
footprint, network isolation, private Bass-stem fidelity, or playable
Rocksmith 2014 CDLC. Do not remove model preflight or user owner controls.

Primary API references:
- https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_process_id_list
- https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-queryinformationjobobject
- https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-getprocessmemoryinfo
- https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/gpu-process-memory-counters-report-wrong-value
