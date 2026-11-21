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
  differential harness). Destinations under the project must be inside
  `review/`; destinations inside the upstream source folder are refused.
  Existing files are replaceable **only** when already a recognized
  auto-cdlc oracle report. Report publication is atomic and cannot overwrite
  original project audio, Bass notes, tempo maps, or an unrelated personal file.

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

## Synthetic known-truth audio benchmark (next bounded slice)

A self-contained, reproducible fixture now separates musical **truth** from
agreement between two transcription pipelines:

- `cdlc-auto-cdlc-truth generate --out-dir DIRECTORY` writes a real,
  original, copyright-free 44.1 kHz PCM WAV plus `fixture.json`. It has
  a precisely sampled **7.130 s** first note and first beat, 40 beats at
  120 BPM with a repeating eight-note riff, accented downbeats, distinct
  note lengths, and a four-beat Bass silence while the click continues.
  Its 4/4 meter and sample coordinates are independent of any transcription.
- `verify_known_truth()` regenerates the **complete WAV byte stream**
  and note/beat timestamps from a pinned code profile
  (`two-bar-phase-sentinel-v1`). It checks the WAV SHA-256 and exact
  event sidecar. Edited/forged truth files are rejected before scoring.
- `cdlc-auto-cdlc-truth evaluate --fixture-dir DIRECTORY
  --upstream-dir UPSTREAM_DIRECTORY --out REPORT.json` evaluates the
  produced audio `*.mid` and `*.svl` against that known truth (the
  upstream model must run separately). Optionally use `--local-project
  PROJECT` to grade the generator's `analysis/bass_raw.json` and
  `tempo_map.json` on the exact same original WAV. Either engine can
  be evaluated alone, or both independently.
- For each engine, the report measures exact-octave note F1, absolute
  first-note phase, note-onset MAE, note-duration MAE, longitudinal
  timing drift, beat/downbeat F1, and **first beat/downbeat phase**.
  This last part is essential: periodic beat matching can have excellent
  F1 while its entire grid is displaced by one or two measures. The
  comparator **never subtracts a best-fit global note or beat offset**.
  It uses the already established `benchmark.evaluate_chart` plus the
  order-preserving `corpus_differential` metrics.
- Threshold scoring applies **only** to this checked original synthetic
  WAV. `fixture_verdict=PASS` is not a statement about commercial
  music, score-to-recording alignment, multi-instrument parity, game
  packaging, or actual Rocksmith playability. The output explicitly
  marks both external engines' artifact-to-input binding as
  `UNPROVEN`; matching the fixture's audio and manifest SHA does not
  cryptographically attest how the engine produced its output.
- The exported JSON contains counts, aggregate metrics, failure codes
  and hash fingerprints only. It excludes song names, raw events,
  private paths and source audio bytes. A report cannot overwrite
  fixture files, upstream exports, local project assets, or unrelated
  existing personal files; replacement of a recognized previous report
  is atomic. Original fixture files and test results must stay outside
  the Git checkout.

Example workflow (PowerShell):

```powershell
cdlc-auto-cdlc-truth generate --out-dir "C:\MusicBench\known-truth"
# Run the independently approved upstream engine on the generated WAV.
cdlc-auto-cdlc-truth evaluate --fixture-dir "C:\MusicBench\known-truth" --upstream-dir "C:\MusicBench\upstream-results" --out "C:\MusicBench\known-truth\reports\run.json"
```

This slice makes objective *synthetic* comparison repeatable. It does
**not** run auto-cdlc's noncommercial-model-dependent transcription,
install Wwise or qualify the owner's private music corpus. Those remain
separate acceptance work on #772/#612. The upstream output's count-in
and added-silence normalization are still enforced by the existing
`auto_cdlc_oracle` parser.

## Pinned upstream synthetic-execution lane (third integration slice)

The `cdlc-auto-cdlc-run` CLI connects the verified original WAV to an
**externally installed** auto-cdlc Python 3.13 checkout. Unlike a simulated
output adapter, this invokes the actual `cdlc_bajo.py` using its documented
`--sin-internet --sin-actualizar --sin-psarc --sin-preguntas` options. It
then measures the actual exported `*.mid`/`*.svl` against regenerated
known-truth audio and writes private, digest-pinned execution evidence.

**Mandatory preflight:**

- Explicit, clean checkout at the reviewed upstream commit
  `cd7826f6a05a9acf8ff1825d52af9e2656d27d01`. No automatic Git
  checkout or unreviewed updates; tracked source modifications are refused.
- A user-provisioned Python **3.13** executable, with upstream dependencies
  and local model caches ready. The wrapper does not install Python,
  dependencies, models or proprietary tooling. It checks the interpreter
  version and records its binary SHA-256.
- An explicit `--confirm-noncommercial` switch, because upstream madmom
  model weights are licensed CC BY-NC-SA. Do not use in a commercial
  pipeline without an independent rights assessment.
- At least **7.0 GiB of free physical RAM** and **8.0 GiB of free disk**.
  A low-memory laptop is refused before any new run directory is created.
  There is deliberately no override to starve the active autonomous
  development engine.
- A *new* run directory outside the Git checkout, upstream source and
  original fixture; source waveform and checksum verified before execution.
  The program operates **only on the generated original WAV**. It cannot
  be pointed at the user's private commercial music through this API.

Run after one-time trusted runtime provisioning:

```powershell
cdlc-auto-cdlc-truth generate --out-dir "C:\MusicBench\truth"
cdlc-auto-cdlc-run --fixture-dir "C:\MusicBench\truth" --upstream-checkout "C:\Tools\auto-cdlc-reviewed" --python-313 "C:\Tools\auto-cdlc-venv\Scripts\python.exe" --run-dir "C:\MusicBench\runs\run001" --confirm-noncommercial
```

On normal completion, `run001/upstream_run_evidence.json` records the
reviewed upstream commit, script hash, exact Python binary hash,
synthetic source fingerprint, model-admission memory, subprocess exit,
and generated artifact hashes; `run001/benchmark.json` contains the
existing sample-clock notes and beats metric report. Both reports stay
on the local machine; there are no game installation actions. Nonzero
exit codes, timeouts, changed source, ambiguous outputs and corrupted
truth reject the run with a **FAIL** receipt.

**Network/privacy boundary:** `--sin-internet` and
`--sin-actualizar` disable upstream metadata, updater and telemetry
paths, and `HF_HUB_OFFLINE` and `TRANSFORMERS_OFFLINE` are exported
to the subprocess. But these flags are **not OS-level network
isolation**; a third-party model loader may still attempt to retrieve
uncached weights. The runner's input is therefore deliberately limited
to the original **non-private synthetic WAV**. A genuinely offline
private-song transcription path needs separate process/container
network controls and externally provisioned, license-reviewed models.
Do not call this a privacy guarantee for arbitrary commercial music.

**Current execution status (2026-11-21):** Azathoth has Python 3.13,
but the inspected laptop has approximately 4.7 GiB RAM available,
below the fail-closed 7.0 GiB floor. Neither a pinned approved
auto-cdlc runtime/model environment nor Wwise was verified in the
standard tool/path checks. This PR tests runner control logic with
mock subprocess outputs; it **does not** imply the upstream model was
executed successfully on Azathoth or that Wwise was installed.

## Read-only environment doctor and fail-closed cached-model gate

The pinned runner now shares a no-install **standard-library-only** preflight
with a separate `cdlc-auto-cdlc-doctor` command. It prints sanitized JSON
to stdout and returns exit 2 when any requirement for the synthetic model
run is absent, exit 0 when the prerequisites pass, or exit 1 on an
operational diagnostic error. Example:

```powershell
cdlc-auto-cdlc-doctor --fixture-dir "C:\MusicBench\truth" --upstream-checkout "C:\Tools\auto-cdlc-reviewed" --python-313 "C:\Tools\auto-cdlc-venv\Scripts\python.exe" --run-parent "C:\MusicBench\runs"
```

The doctor verifies regenerated original-WAV SHA-256, a clean checkout
at the pinned reviewed upstream Git SHA, Python 3.13 package metadata
(without importing heavy models or running pip), a cached MDX Bass ONNX
file, and Beat This!'s >=50 MB cache file with the **exact expected
source-defined SHA-256**. It checks at least **7 GiB free physical RAM**
and **8 GiB free disk**, and separately reports whether a WwiseConsole.exe
is located. Wwise visibility **never** means a WEM, PSARC or gameplay test
has passed. The ONNX SHA is recorded but has no authoritative expected
hash, so its provenance is not established merely by its presence.

The real `cdlc-auto-cdlc-run` now **requires this same inspection**
before invoking upstream code. Offline/update-suppression flags do not
prevent all third-party model loaders from trying to fetch missing
weights, so absent or invalid local caches must block the run.
The doctor does not download/install anything, modify the game, read
private music, execute models, create files, or upload telemetry. The
proposed heavy-model execution remains synthetic-audio-only;
OS-level network isolation is not yet proven.

**Observed Azathoth, 2026-11-21:** the available Python 3.13.17
interpreter lacked `audio-separator`, `madmom`, `beat-this`,
`torchcrepe` and `librosa`. A pinned upstream checkout and Wwise
were not found in the inspected standard directories. Available RAM
reached ~2.1 GiB during inspection. These are genuine environment
blockers, not evidence that a real upstream model has succeeded.
## Outstanding integration and acceptance work

*The artifact parser and a reproducible known-truth fixture/metric harness are implemented; actually running upstream models and independently verifying upstream provenance/real-song accuracy remain outstanding.*



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
