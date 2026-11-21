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

## Implemented next slice: independent MIDI/SVL clock oracle (#772)

`cdlc-auto-cdlc-oracle` consumes **actual** upstream exported
`*.mid`, `*.svl` and `diagnostico.json` files (the upstream audio
model or installer is *not* executed). It compares those against
`analysis/bass_raw.json` and `analysis/tempo_map.json` in the local
Rocksmith project using our existing non-authoritative Tier C
`corpus_differential` and absolute-clock one-to-one beat matching.
Both inputs are independently loaded; the adapter **never alters or
promotes** score timing, chart notes, validation state or the game.

Upstream source inspection explains a crucial clock asymmetry:

- Upstream `cdlc_bajo.py:2001-2026` writes the Sonic Visualiser
  `*.svl` using a **four-beat COUNT + additional lead-in silence**.
  The exact added silence (seconds, rounded to milliseconds) is stored
  in `diagnostico.json -> resultado.silencio_inicial_s`.
- Upstream `cdlc_bajo.py:2119-2127` separately writes the raw Bass
  `*.mid` on the **original recording clock**, not on the `*.svl`
  padded clock.
- Our parser requires the expected count-in pattern `1,2,3,4`,
  removes those four artificial beats, subtracts the recorded silence
  from the remaining `*.svl` beat positions, and rejects ambiguous or
  malformed data rather than fitting a convenient global shift.
- It accepts standard MIDI note-on/off events with tempo changes and
  performs **octave-correct** pitch comparison; no modulo-12 shortcut.
  The existing corpus comparator handles repeated riffs without
  allowing them to conceal first-entrance phase displacement.
- Reports store only aggregates, source/build file hashes and named
  diagnostic alerts, never song names, lyrics, note arrays, local paths
  or exact event timestamps. Input and output files stay local. Output
  is refused inside a Git checkout (same policy as the private corpus
  differential harness).

The command requires the original recording supplied to auto-cdlc as
`--upstream-audio` and confirms it matches the project's immutable
source SHA-256. **This does not cryptographically prove that the
upstream diagnostic/MIDI/SVL actually came from that recording**:
upstream's output lacks that source binding. Consequently, reports are
always `REVIEW_REQUIRED` even if both engines agree. This is an
automated diagnostic, **not an independent ground-truth oracle or a
musical PASS**. To upgrade authority, future producer-side provenance
must capture original input hashes at generation time and a trusted
reference/known-truth fixture must be available.

```powershell
cdlc-auto-cdlc-oracle `
  --project "C:\\MusicProjects\\Song" `
  --upstream-dir "C:\\auto-cdlc\\salida\\Artist - Song" `
  --upstream-audio "C:\\Music\\original.mp3" `
  --out "C:\\MusicProjects\\Song\\review\\auto_cdlc_differential.json"
```

The CLI returns exit code 3 for an intentionally non-authoritative
`REVIEW_REQUIRED` diagnostic, 1 on malformed input, and writes the
local JSON report only when all basic input/provenance checks pass.

Synthetic tests include consistent input clocks, a +4.0-second
two-bar/repeated-phrase shift, octave disagreement, malformed count-in,
unsafe XML entities, source mismatch, ambiguous MIDI inputs and report
sanitization. They demonstrate **adapter semantics**, not measured
upstream real-song correctness or an installed Wwise/auto-cdlc model
runtime.

## Outstanding integration and acceptance work

*The parser/diagnostic portion of items 1-2 is now implemented; running upstream models and independent known-truth acceptance remain outstanding.*



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
