# Candidate Bass source-separator model cards (issue #796, slice 20)

**Scope:** published model-card/format/rights comparison only. No local model or media was installed, downloaded, loaded or executed. No Windows CPU/DirectML fit, peak host RAM, local pinned cache, network isolation, licensing entitlement or Bass-note accuracy is established. The comparison is machine-validated by `bass_model_candidates.py` and negative regression tests.

## Evidence-driven comparison (2026-11-21)

| Candidate (specific published artifact) | Family | Published size | Outputs | Rights status | Windows on Azathoth |
|---|---|---|---|---|---|
| HTDemucs ONNX `fp16weights` | Hybrid Transformer Demucs | 166 **MB** | Drums, **Bass**, other, vocals | Publisher says ONNX MIT; exact local weight terms not independently reviewed | **Unverified** ONNX runtime and RAM |
| HTDemucs FT Bass-specialist ONNX `fp16weights` | Hybrid Transformer Demucs | 166 **MB** | **Bass** | Same licensing re-verification required | **Unverified** ONNX runtime and RAM |
| HTDemucs 6s ONNX `fp16weights` | Hybrid Transformer Demucs | 136 **MB** | Drums, **Bass**, other, vocals, guitar, piano | Same licensing re-verification required | **Unverified** ONNX runtime and RAM |
| BS-RoFormer-SW MLX `float32` | Band-split RoFormer | 666.5 **MiB** | Bass, drums, other, vocals, guitar, piano | Weight license **unknown** in pinned source catalog | Apple Silicon MLX, **not Windows** |
| UVR MDX-Net Inst HQ3 MLX `float32` | MDX-Net | 63.8 **MiB** | Instrumental, vocals | No weight-specific redistribution license in catalog | **Not a Bass-isolation model**; Apple Silicon MLX |

The sizes refer to the **specific distributor and published serialized format**, not native checkpoint equivalence, and **cannot be substituted for peak inference RAM or GPU VRAM**. The ONNX `fp16weights` variant computes in FP32 according to its publisher. The single guitar stem in six-stem models is not independently verified Lead/Rhythm separation.

**Primary evidence and source boundaries:**
- [StemSplit's Demucs ONNX model-format/size/model list](https://stemsplit.github.io/demucs-onnx/models/) — 166/136 MB ONNX `fp16weights`, separate FT Bass specialist, claimed ONNX MIT licensing.
- [Original Demucs repository](https://github.com/facebookresearch/demucs) — four- and six-source models, command behavior, segmented inference, GPU memory caveats and code MIT terms.
- [MLX separator model catalog](https://huggingface.co/ssmall256/mlx-audio-separator) — 666.5/63.8 MiB *MLX* sizes, Apple Silicon constraints, and output roles.
- [MLX third-party notices](https://huggingface.co/ssmall256/mlx-audio-separator/blob/main/THIRD_PARTY_NOTICES.md) — model-specific rights ambiguities; software/code MIT license alone does not establish every checkpoint's weight license.
- [audio-separator upstream README](https://github.com/nomadkaraoke/python-audio-separator) — default behavior downloads an absent model automatically; do **not** run it without the repository's independent pre-admission and OS network boundary.

## Engineering next-step order

1. Start with an **ONNX Bass-capable source** for *further investigation*, not a runtime approval. Pin one exact upstream artifact and its license text, supporting files, SHA-256, transitive dependencies and provenance; do not infer rights from the file suffix.
2. Determine whether the current `cdlc separate-bass` adapter can use it safely. A different runtime/format demands a separately reviewed adapter and fail-closed boundary; changing the name in the manifest does **not** make an incompatible runtime work.
3. Require verified offline network containment, owner-approved execution, >=7 GiB *available physical* RAM, >=8 GiB disk, whole-child-tree memory controls, and bounded synthetic audio/source-geometry tests before any local model launch. The historical Windows Home network-isolation gap remains open.
4. Evaluate on lawful independent Bass onset/pitch truth, source-stem phase and negative controls; never promote zero confidently qualified pYIN notes, or claim the historical two-bar timing regression resolved on software-only tests.

The machine-readable catalog `engineering/bass-separator-model-candidates.json` intentionally has `approved_for_execution=false` for **every** row and a real instrumental-only negative control. Run the read-only comparison using `python -m rocksmith_cdlc_generator.bass_model_candidates`. This does not touch private media or download weights.
