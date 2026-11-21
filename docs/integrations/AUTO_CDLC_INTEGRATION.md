# auto-cdlc upstream integration: guarded, evidence-first adoption

## Source and licensing review (2026-11-21)

- Upstream: [fesaje/auto-cdlc](https://github.com/fesaje/auto-cdlc)
- Reviewed commit: `cd7826f6a05a9acf8ff1825d52af9e2656d27d01`.
- Inspected: `README.md`, `docs/en/how-it-works.md`, `docs/en/usage.md`,
  `THIRD_PARTY.md`, `desarrollo/pruebas/evaluar.py`,
  `cdlc_bajo.py` (`construir_grid`/`cuantizar`), and
  `herramientas/cdlc-pack/codigo/Program.fs`.
- Upstream code license: MIT, while individual dependencies keep their own
  licenses. Upstream `madmom` **models** are CC BY-NC-SA; importing the
  complete Python music-analysis stack into this project is **not authorized**
  by this PR. `Rocksmith2014.NET` is independently MIT-licensed.
- This repo does **not** vendor upstream files, redistribute an executable,
  add Python 3.13 dependencies, download a model, or modify the game.
  External binaries remain an explicitly configured local runtime input.

## Implemented first slice: optional cdlc-pack execution

`cdlc build-psarc` supports the upstream F# `cdlc-pack.exe` argument contract
(`project.rs2dlc --salida DIRECTORY [--wwise WwiseConsole.exe]`) without
invoking DLC Builder's GUI. The upstream tool uses DLC Builder's
`Rocksmith2014.NET` functions to convert audio with Wwise and build a PC
PSARC. We **do not** treat its console `VERIF` output or exit code alone as
proof of a good package: upstream's `Program.fs` logs some SNG read-back
exceptions without changing the overall exit code.

### Preconditions

1. Generate a validated `*.rs2dlc` project with the existing
   `cdlc prepare-dlcbuilder PROJECT` flow.
2. Obtain/build a trusted, locally approved `cdlc-pack.exe` from the reviewed
   upstream source; keep it **outside** this repository and the game directory.
   Do not auto-download or auto-update third-party executables.
3. Install the compatible Wwise tooling and the existing pinned PSARC
   inspection bridge (`scripts/bootstrap_psarc_bridge.ps1`).
4. Compute the actual executable hash locally:
   `(Get-FileHash "C:\\Tools\\cdlc-pack.exe" -Algorithm SHA256).Hash.ToLowerInvariant()`
5. Invoke an opt-in local build (the pinned hash is mandatory):

```powershell
cdlc build-psarc "C:\\MusicProjects\\Song" `
  --packager "C:\\Tools\\cdlc-pack.exe" `
  --packager-sha256 "<64 lowercase hex SHA-256>" `
  --wwise "C:\\Program Files\\Audiokinetic\\Wwise XXXX\\Authoring\\x64\\Release\\bin\\WwiseConsole.exe"
```

The Wwise argument is optional if the upstream packager reliably discovers
the local installation. Pin exact tool versions and hashes for real-machine
acceptance before generalizing compatibility.

### Machine-enforced gates

- Explicit local `.exe` path and SHA-256 pin, plus a working independent PSARC
  inspection bridge, are checked **before** staging.
- The existing arrangement-readiness gate must PASS for *all configured*
  Bass/Lead/Rhythm roles (never silently downgrade to bass only).
- `stage_build()` creates a new package generation and hashes the `.rs2dlc`
  project, chart XML, audio, preview and artwork. Output is forced beneath
  `PROJECT/build/staging/cdlc_pack_output`, never the live game DLC path.
- The external process is invoked with an argument list (`shell=False`),
  a bounded timeout and captured diagnostic tails; no updater or reporting
  service is called by this adapter.
- Nonzero exit, an upstream `VERIF error=` line, a missing/multiple/non-PC
  output, stale source hashes or changed package generation **fail closed**.
- A single new `*_p.psarc` is passed to our independent `register_psarc()`
  and `verify_psarc_registration()`. Our pinned bridge must inspect the
  archive's configured SNG roles, manifests, WEM, sound bank, xblock and artwork.
- Only a current, deep-verified `psarc_receipt.json` may report
  `safe_for_manual_installation=true`. This is **not** a claim of musical
  correctness, actual Rocksmith gameplay, or owner approval to install.
- Local `cdlc_pack_run.json` records the binary SHA, generation, build result
  and bounded diagnostics. It is private build output, not a Git artifact.

The adapter does not run automatically during song processing or activate
on the unattended worker until a representative private Windows/Wwise
acceptance scenario proves it on the **exact build**. The CLI opt-in is a
functional integration, not a verified production default.

## Next bounded integration slices (not implemented in this PR)

1. **External beat/transcription oracle, not authority.** The upstream
   `madmom + Beat This!` pipeline and `pYIN/CREPE` Bass transcription
   could produce independently measured beats/downbeats/onsets/notes.
   Compare against our canonical score-to-recording phase and existing
   independent EOF oracle on identical synthetic or lawful private fixtures.
   Never copy upstream quantization offsets into our shared timing transform
   without proof.
2. **Strengthen the benchmark.** Upstream
   `desarrollo/pruebas/sintetico.py` and `evaluar.py` provide synthetic
   Bass/drum cases, beat and downbeat F1, note-onset F1 and repeated-note
   recall. Its note evaluation currently permits a best-fit global shift
   and checks pitch classes modulo 12; our benchmark must additionally test
   absolute first entrance, octave-correct pitches, sustained note ends,
   two-bar repetition ambiguity, drift at later landmarks, and all three
   arrangement roles.
3. **Practice and authoring utilities.** Assess `*_AB.mp3` (real Bass vs
   synth), `*_clics.mp3`, GP5/SVL export, phrase-level Dynamic Difficulty,
   album/artist batching, and optional tone reference metadata against our
   own existing functionality. Integrate only measurable gaps.
4. **Private unattended Windows acceptance.** Wire a pinned toolchain into
   `cdlc-local-worker` scenarios with sanitized, exact-head evidence and
   no media egress. Require a real Wwise conversion, deep PSARC inspection,
   deterministic score/audio checks and owner-operated gameplay acceptance
   where legitimately necessary.
5. **Licensing and model/runtime gate.** Resolve noncommercial model terms,
   compatible Python 3.13 isolation, CPU/RAM budget, and algorithmic error
   profiles before any music-model component is admitted into the main runtime.

## Outcome boundaries

The desired end state remains validated Bass + Lead + Rhythm, unattended
objective tests, source provenance, and human-only final musical judgment.
Neither the upstream project's reported per-song speed nor its automatic
transcription accuracy has been independently reproduced by this PR.
