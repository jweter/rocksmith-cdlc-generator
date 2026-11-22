# Host concurrency admission — canonical #796 slice 21

Status: **bounded code-level implementation; model runtime and Product Reality remain unproven**.

## Why the previous readiness snapshot was insufficient

The optional `cdlc separate-bass` path already checked available **physical**
RAM before its project/model/manifest preparation. After that successful check,
other workloads (e.g. audio production or the user's local development engine)
could consume RAM before the actual `subprocess.run` starts. A stale ADMITTED
preflight was therefore unsafe as the only concurrency sensor.

## Implemented in the actual optional separator adapter

- Standard-library, read-only `inspect_host_concurrency` samples total host
  **available physical** RAM three times over two 50-ms intervals immediately
  **before** the real optional separator subprocess call. Available physical
  RAM reflects pressure from all workloads; no private process names, PIDs,
  content, source paths or memory maps are collected.
- Keep the existing 7-GiB pilot floor and add 0.5 GiB conservative transient
  headroom, requiring >=7.5 GiB at **every** sample. The margin is a safety
  buffer, not a measured model-RAM footprint or proof that another process
  will not allocate more memory after sampling.
- One low/freefall sample, invalid/boolean/text/NaN memory measurement,
  exception or unavailable probe **DEFER**. Never average a low sample away,
  never convert failed telemetry into permission, and never use swap or total
  installed RAM as the admission variable.
- The check is in the **real**
  `AudioSeparatorBassStemSeparator.separate` code path, after explicit
  cached-model/owner execution gates and just before subprocess creation.
  Previously admitted projects therefore cannot bypass a later host
  resource drop simply because model files and licensing inputs were once
  valid.
- Synthetic regressions include 9->6.5->9 GiB mid-check collapse,
  9->8->7.4 GiB last-sample collapse, missing sensors, bogus high/boolean
  input, bounded sample count, sanitized public evidence, and an actual
  adapter test proving `subprocess.run` is **never called** under host
  memory pressure.

## Critical limits

This is **not** a model pilot, OS-enforced continuous RAM budget or a
Windows Home network sandbox. The 100-ms sampling window cannot guarantee
the RAM floor stays available after the model starts, cannot independently
identify which process consumed RAM, and does not sample model GPU/VRAM or
prove source-separation quality. A future resource-watchdog and enforceable
process-tree control are needed before approved heavy inference. No model,
commercial audio, user laptop manual test, model install or download was
used for this engineering slice.

The normal owner execution switch, cached model SHA, model rights review,
network-isolation and private Bass note verification requirements are
unaltered. This work provides **advisory resource deferral**, not
`model_execution_authorized`, `network_isolation_proven`, or musical PASS.
