# Safe Bass separator pilot — local cache and resource admission

Implementation: `bass_separator_admission.py`, `stems.py`, `cdlc separate-bass`.
Tracking: #787, #612, #772.

## Why this exists

The optional `audio-separator` CLI normally resolves a model filename by
looking in its model cache, and **may automatically download a missing model**.
Running the preexisting `cdlc separate-bass` directly could therefore cause
unexpected downloads, consume RAM, and overwrite `stems/bass.wav` without
recording whether a model was locally approved. This is unsafe for a busy
~16-GiB Windows development laptop.

The command is now **readiness-only by default**. It never downloads or
installs a package, runs inference or mutates song files in that mode.

## Local pilot requirements

1. A deliberately selected model filename *ending in* `.onnx`, `.pth` or
   `.ckpt`, found as a regular (not symlink) file under an **explicit
   model-cache directory**. The caller supplies the **expected SHA-256**. Since PR #800, a separate in-cache `--model-manifest` JSON must also list each declared auxiliary artifact with a pinned SHA-256/size. This verifies only declared files, not unknown upstream dependencies.
   A model config requiring extra weights is not treated as sufficient proof
   of a self-contained local inference setup.
2. Explicit acknowledgment of acceptable model license and rights.
3. The `audio-separator` CLI must already be present; no pip install,
   model download or environment creation is performed.
4. Normalized private input is uncompressed 16-bit PCM WAV, no longer than
   45 seconds (short experimental pilot only). Whole-song inference needs
   a separately validated streaming/chunked worker.
5. **At least 7 GiB available physical RAM** and **8 GiB free disk**,
   checked before launching; total installed RAM and swap do not count.
6. Explicit `--execute` to start the timed, local model process.
7. The input WAV and cached model file must match their hashes before and
   after model execution, and the WAV result must match original rate,
   frame count, channels and PCM layout before an atomic replacement of
   the Bass stem and its provenance receipt.

Readiness-only example (paths are illustrative):

```powershell
cdlc separate-bass C:\RocksmithLocal\synthetic-project `
  --model bass-model.onnx `
  --model-cache-dir C:\RocksmithLocal\models `
  --model-sha256 <64-character-verified-digest> `
  --confirm-model-rights
```

**Execution is intentionally separate:** add `--execute` only for an
explicitly approved cached model, after the readiness result is ADMITTED.
The process has a bounded 30–900-second timeout (default 240). It runs
without exposing stderr in reports and requests offline use via environment
hints (`HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE`,
`AUDIO_SEPARATOR_MODEL_DIR`) and an explicit `--model_file_dir` CLI flag.

**Critical limitation:** These environment flags are **not OS-enforced
network isolation**; upstream could still request model metadata, update
files or make network requests. Until an independent network sandbox and
complete model dependency manifest are verified, do not claim that executing
the external separator is definitively offline. A local file+hash alone does
not prove model quality or absence of auxiliary downloads.

## What the code does and does not prove

- It **does** reject missing/unpinned cached models, missing CLI, unknown
  licensing acknowledgment, insufficient RAM/disk, overlong songs and
  mismatched output geometry; it preserves previous stem and receipt on
  failed preparation. It records the model SHA-256 in the stem provenance.
- It **does not** install a model, measure GPU/child process peak RAM,
  continuously enforce a physical RAM ceiling, prove isolated Bass purity,
  ensure pitch correctness, repair score timing or validate gameplay.
  This is an execution-safety first slice, not a completed musical pipeline.
- The private project/audio, model cache, and original song stay local.
  No commercial audio or model weights enter GitHub.

## Verified Azathoth environment observation

A read-only probe on 2026-11-21 observed ~5.87 GiB available physical RAM
of 15.72 GiB installed, ~29.11 GiB free on C:, Python and FFmpeg present,
no `audio-separator` executable on PATH, and no installation in default
Python. Two common model cache directories had no cached model files.
**Therefore the proposed model pilot is currently BLOCKED, and no model
was installed, loaded or executed on Azathoth.** Absence in the checked
locations does not prove that no model exists anywhere else.

## Next acceptance

Use the current #791 synthetic-known-truth three-source comparison only
after explicit model-license approval, a pinned and verified cached model,
a measured resource envelope, and independent network controls. Instrument
stem output is **read-only evidence**, never a basis to bypass #790 content
clock qualification or the project's score-human-review gate.
