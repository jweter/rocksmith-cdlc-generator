# Rocksmith CDLC Generator — Canonical Roadmap

## Owner-approved milestone emphasis (2026-10-25)

Prioritize a usable end-to-end Windows workflow: import song and complete score where available, create reviewed Bass/Lead/Rhythm arrangements, validate, export, and verify game-compatible packaging. Preserve the canonical detailed roadmap, musical correctness, human review, licensing and private-library safety, and actual Product Reality gate. See `docs/OWNER_APPROVED_ROADMAP_2026-10-25.md`.


This file is the canonical implementation roadmap. The product goal is a real Windows desktop application that turns one local song recording plus one complete structured score, when available, into reviewed Rocksmith 2014 Bass, Lead, and Rhythm arrangements with as little manual authoring as practical.

The GUI is the primary product. The CLI remains the deterministic engine/debugging surface.

## Next Product Reality blocker: full-mix audio note confidence (2026-11-21)

The **automatic local worker is functional** (#783, #784) but produced six
`REVIEW_REQUIRED` recent-project views (four distinct recordings).
Unlike the original approximately two-bar mapping bug, this is a
**quality-of-evidence limitation**, not a measured drift: all six have
hundreds of existing pYIN Bass note candidates analyzed from the
full-band `normalized.wav`, zero confidently qualified audio note
events, and no isolated bass stems. Full-mix pYIN is not a fit-for-purpose
independent Bass oracle in this setting. A private 12-second,
resource-bounded comparison on Azathoth measured 20 original / 33
230-Hz-filtered / 29 430-Hz-filtered candidates, but **0/0/0 strong
notes**; simplistic low-pass cannot safely fix the confidence gap.
Do not lower note confidence thresholds, infer global alignment from
0 reliable events, label any musical test PASS, or ask the owner to
manually repeat the same known-failing check.

**Release/acceptance (2026-11-21, merged #785):** PR #785 delivered
typed audio-gap diagnostics and deduplicated source counts in merged
`c7527c9db395bb519311fc2ec5bbb7ec33989817`. Fresh exact-head
CI passed 2,403 Python tests, Windows Desktop packaging, and the pinned
PSARC bridge; the only material code-review finding (silent omission
of malformed Bass JSON) was repaired and has a real worker-level
regression. After installing the exact build on Azathoth, the existing
Windows Task Scheduler task launched it **automatically** on the
06:38 CST timer, with exit code 0 and an independently build-bound
scheduler heartbeat. The report classified all six project views as
`FULL_MIX_PYIN_UNQUALIFIED`, with only four unique recordings. This
closes the *diagnostic automation* slice, not the missing bass-stem
evidence, historical two-bar timing issue, Wwise/gameplay testing or
Bass+Lead+Rhythm correctness.

**First shippable slice:** machine-readable, privacy-safe
`audio_evidence_gap` diagnostics plus exact recording-hash
deduplication **for reporting only**. Preserve every separate project's
score-to-recording qualification; do not deduplicate test verdicts
where source versions/authorities differ. Stable codes distinguish
full-mix pYIN unqualified, an existing untranscribed bass stem, an
unqualified separated stem, missing/unreadable evidence, and ambiguous
alignment. Classify the missing *automatable capability* in local
evidence instead of recurring human escalation.

**Following audio-oracle slice:** evaluate a locally licensed,
resource-admissible Bass source separator and independent stem
transcription in a private sidecar, with source WAV/stem content hashes,
recording-clock continuity, strict unchanged evidence thresholds, no
overwriting original project transcription, and original public-domain
or synthetic false-positive controls. Prove real-song two-bar mismatch
detection and negative cases with multi-event Bass onsets, retaining
Lead/Rhythm role parity; models never become automatic workers merely
because a diagnostic says `PRIVATE_BASS_STEM_SEPARATION`.

## Instrument Audio Evidence — near-term engineering order (2026-11-21)

**Merged #788:** The Arrangement Preview now has tuning-aware original/focused/stem
audio audition and measured short-time spectrum beside selected Bass/Lead/Rhythm
notes. This is a listening/visualization foundation, **not** a proven pitch detector
or source separator.

**Trust gate merged (#787, #789):** Bass reconciliation v3 requires a
current hash-bound isolated Bass stem, exact original-sample geometry, independent
pitch/timing/overall confidence and recording alignment before promotion to
`symbolic_verified`. Full-band/filtered pYIN evidence remains review-only even
if it reports many candidate notes. Pre-v3 generated reconciliations become stale.

**Content-clock audit merged (PR #790):** A bounded, dependency-light
analyzer measures up to +/-250 ms of Bass stem content delay from multiple
independent low-frequency audio windows. It requires a clear, repeatable
correlation peak and writes a private, current-input-hash-bound
`analysis/bass_stem_content_alignment.json` diagnosis during reconciliation.
Aligned content is an additional prerequisite for Bass note verification;
shifted, silent, conflicting or incompatible evidence cannot promote a note.
This does **not** auto-correct timing, claim a source is isolated, or qualify
the historical two-measure score-to-recording error. Synthetic 0/40/200 ms
and negative controls are in the automated regression tests; external
model/private-song musical accuracy still needs independent testing.

**Source-comparison benchmark (#791, implementation pending exact-head checks):**
A new offline `cdlc-bass-evidence-compare` command uses the existing original
synthetic 7.130-second entrance fixture and `BenchmarkChart` scorer to compare
the original mix, an existing provenance-bound frequency-focused WAV and an
existing hash-bound Bass stem. By default it only checks readiness; running
pYIN requires an explicit `--execute` plus >=4 GiB available physical RAM,
>=2 GiB free disk and <=45 seconds/30 MiB original PCM. The tool does not
launch a separator or install/download models, writes no private audio to Git,
and never claims source-isolation, real-song or gameplay PASS. Reports distinguish
raw note F1 from independently confidence-qualified note F1, preserving
source hashes and missing/misaligned stem reasons. See
`docs/engineering/bass-source-evidence-benchmark.md`. Next: validate an
explicitly licensed local model under its *separate* RAM/cache policy before
promoting source-separation accuracy.

**Safe separator admission (#792, code-level validation pending):** The
existing `cdlc separate-bass` is readiness-only by default, and requires an
explicit previously cached local model, expected model SHA-256, license-rights
confirmation, `--execute`, >=7 GiB available physical RAM, >=8 GiB disk,
a <=45-second normalized original WAV, a bounded timeout, and output PCM
geometry verification before replacing private stem/receipt files. It cannot
install/download a model itself. External library offline hints are not
OS-enforced network isolation, and no model peak RSS, separation quality, or
real-song musical correctness is proven. Read-only observation on Azathoth
(2026-11-21): ~5.87 GiB available physical RAM (15.72 total), ~29.11 GiB
C: free, no audio-separator CLI/default Python package, and no cached models
in two checked default locations. Thus **no heavy inference was started**.
See `docs/engineering/safe-bass-separator-pilot.md`.

**Next highest-value musical proof:** Extend the existing #775 known-truth
synthetic generator plus the existing benchmark evaluator, not a parallel scoring
framework. Test true bass/guitar/drum mixtures, intentional stem processing
delays, octave confusion, tuning/drop tuning, polyphony and off-score silence.
Then separately admit a resource-safe local Bass separator and measure validated
note precision/recall and onset accuracy under the same gates. Do not relax #612
acceptance, owner approvals, or available-memory admission.

See `docs/engineering/evidence-first-audio-ideas-and-acceptance.md` for the
ranked ten-slice backlog and independent fail-closed acceptance criteria. A
short display spectrum (currently 0.18 s) cannot by itself resolve adjacent
low Bass semitones, and matching stem frame counts do not prove content latency.
These are explicit future tests, not musical PASS claims.

## auto-cdlc upstream integration (owner-approved 2026-11-21)

**Source:** [fesaje/auto-cdlc](https://github.com/fesaje/auto-cdlc) at reviewed
commit `cd7826f6a05a9acf8ff1825d52af9e2656d27d01`. This is an
**optional, license-aware reusable reference** for the current Product Reality
milestone, not a replacement for the canonical Bass + Lead + Rhythm
generator or its review, authority and validation gates.

**Slice A — guarded local packaging (merged in #771; real Wwise acceptance pending):** add a
`cdlc build-psarc` backend for the upstream F# `cdlc-pack.exe`
command contract using an explicit executable path and pinned SHA-256.
Keep the executable outside Git, do not run the updater or import the
upstream Python 3.13 model environment, never install into Rocksmith,
and require independent deep PSARC read-back through our existing
pinned bridge. Reject upstream logged verification errors even when its
process exits successfully. Code-level CI and Windows Desktop checks passed on exact merged head;
a Windows/Wwise/private-lawful-song acceptance remains outstanding.

**Slice B — independent musical benchmark (artifact adapter implemented; real-run acceptance pending):** compare upstream's
madmom/Beat This! beat/downbeat tracking and pYIN/CREPE Bass note estimates
against our source-aligned score and EOF oracle. Establish a fixed first
entrance, repeated-phrase phase, pitch-with-octave, note endpoints and
longitudinal drift test, including the historical two-bar shift. Treat
external output as comparison evidence, never authoritative timing.

**2026-11-21 progress:** a non-authoritative offline adapter now reads
actual auto-cdlc `.mid` and `.svl` outputs plus `diagnostico.json`,
normalizes the SVL's extra 4-beat COUNT and added silence into the
original song clock, and computes absolute beat/downbeat agreement and
octave-correct Bass differential metrics against our analysis.
It preserves Tier C `REVIEW_REQUIRED` and does **not** claim independent
musical truth or run the upstream model. Synthetic mutation controls
cover our historical multi-bar failure class. The upstream model remains unrun; independently authenticated upstream
input/output provenance and real Windows/Wwise acceptance remain for #772.
A bounded synthetic known-truth generator/benchmark was merged in #775: a reproducible, SHA-verified 44.1 kHz original WAV with
7.130 s first entrance, 40 beats, known Bass note durations and a four-beat
Bass silence. It scores upstream and our own audio-derived outputs independently
against the **original sample clock**, including exact-octave note F1,
first onset, onset/duration error, beat/downbeat phase and drift. Synthetic
passes cannot establish commercial-song, three-role, or gameplay readiness.

**Slice C — productivity parity:** assess auto-cdlc synthetic fixtures,
stereo Bass A/B previews, `.svl` beat maps, GP5, Dynamic Difficulty,
batching, per-album tones and diagnostic reliability. Prioritize the
smallest license-compatible measurable improvement over duplicated
architecture, and preserve equal Bass/Lead/Rhythm project targets.

**Slice B execution wiring (owner-approved 2026-11-21):** the
`cdlc-auto-cdlc-run` opt-in command invokes the pinned upstream
Python 3.13 CLI on our verified **original synthetic WAV only**,
requiring explicit noncommercial-model acceptance, a clean reviewed
Git commit, sufficient RAM/disk, and preinstalled model caches. The
runner records process/toolchain SHA-256 and then grades generated
MIDI/SVL against the sample-clock known truth without mixing independent
provenance with importer correctness. A simulated-subprocess regression suite (merged #776) proves
admissibility and failure behavior, not model output quality. On the connected Azathoth laptop, Python 3.13 exists but
free RAM was ~4.7 GiB (below the 7 GiB safety floor); compatible
upstream model caches/Wwise were not verified. Do not launch
heavy models or claim real upstream success while these gates fail.
No per-song human timestamp check is required for this work.

**Merged and laptop-tested evidence (2026-11-21):** #774, #775 and #776
are merged. PR #776 passed 2,329 Python tests and the required Windows
Desktop plus CI bridge checks; latest independent review has no findings.
Azathoth generated the original synthetic WAV from the isolated merged
benchmark source and then successfully exercised the actual fixed PR #776
`cdlc-auto-cdlc-truth generate` command. The WAV SHA-256 was verified,
with 40 beats, 36 Bass events, and first note 7.130 seconds. The active
Rocksmith checkout and its modified preflight evidence were not touched.
The *external* auto-cdlc heavy model remains unrun because the laptop has
fewer than the required 7 GiB free RAM, model caches were not verified,
and a Wwise authoring installation was not found in inspected locations.
These conditions block a truthful full-integration declaration.

**2026-11-21 blocker closure (read-only readiness, merged #778):**
A new `cdlc-auto-cdlc-doctor` returns sanitized machine-readable evidence
for Python 3.13 distribution versions, the reviewed pristine upstream
checkout, pre-cached Bass and Beat This! model files, original synthetic
source authenticity, available physical RAM/disk and optional Wwise
discovery. The real upstream runner now refuses model execution
until the exact same cached-model and resource preflight passes.
Crucially, `--sin-internet` alone is not proof that upstream's
model-loading code will never fetch missing weights. The doctor
performs no installs, network calls, audio-model imports or uploads.
On Azathoth, the actual read-only doctor run exited 2 BLOCKED:
Python 3.13.17 had 0/18 upstream packages; pinned upstream checkout,
cached ONNX/Beat This! weights and Wwise were not found, while the
original synthetic WAV SHA-256 and 31.316 GiB free disk verified.
Available physical RAM was 6.499 GiB (<7 GiB), with previous measured
values as low as 2.09 GiB. Required CI, Windows Desktop and PSARC bridge
checks passed on exact #778 head (2,350 Python tests). Preserve the
no-human timestamp-testing target and do not bypass these gates.
**2026-11-21 unattended worker continuation (merged #780):** the local
read-only `cdlc-auto-cdlc-doctor` is now wired as an explicitly
configured, **non-executing** environment probe in the real
`cdlc-local-worker` idle loop. It records a sanitized separate
`auto_cdlc_readiness` snapshot in the same local latest/history
evidence used for Product Reality; missing cached models, packages,
or RAM do not demote a valid song acceptance result or trigger
repeated Ollama/human testing. Source/code input paths and hash
fingerprints stay out of the worker summary and its optional GitHub
publication. This is preparation for unattended actual-model acceptance,
**not** running the upstream neural networks.

Azathoth's reviewed upstream checkout is now locally prepared at
`cd7826f6a05a9acf8ff1825d52af9e2656d27d01`, with original
`cdlc_bajo.py` SHA-256 `29c4905eb0eba3ac015b3979711b6e1161244bb772abb55c0a13937fa17cf313`.
An isolated Python 3.13.17 virtual environment (without packages or
model weights) passes the environment isolation check. The doctor
verified the upstream Git pin and original synthetic WAV; remaining
blockers were 0/18 dependencies, missing cached model weights, and
available RAM ~6.30 GiB, below the 7 GiB floor. Active source and
its modified preflight evidence were preserved.
**2026-11-21 scheduler-blocker repair (merged #781):** live Azathoth
Task Scheduler inspection revealed the registered `Rocksmith CDLC
Unattended Worker` task is **disabled** and its old executable path
is **missing**. Its last run was 2026-10-12. This is a distinct root
cause from missing ML prerequisites: the idle worker cannot run even
when its code and dependency checks are correct. The registration
function must query the task's XML settings before using
`schtasks /Create /F`. Preserve explicit owner-disabled and
unknown/inaccessible states, and only refresh the current packaged
executable for tasks that are enabled or truly absent. Do not silently
enable the owner's task during an update, bypass the owner pause, or
launch the heavy upstream models. No scheduled task or active
Rocksmith configuration was modified during diagnosis. The safe
owner-disabled preservation and enabled-task refresh were merged in
#781 after 2,371 passing Python tests plus the full required Windows
workflow evidence and clean code review. Azathoth still has the task
disabled, so no recurring monitoring is claimed. A new BOM-free local
worker.json is staged with read-only source, fixture, and Python
prerequisite paths. It becomes useful when the owner explicitly
reactivates a current packaged idle worker; it does not load models.

**2026-11-21 automatic-idle root-cause experiment and resilience slice
(merged #783, real automatic laptop acceptance passed):** after explicit owner approval, the reviewed Windows
artifact `21e44f1` was installed, the Task Scheduler action corrected,
and the task re-enabled. A manual one-time Windows `RunEx` succeeded and
recorded six insufficient-timing-evidence recent projects, plus an
independently BLOCKED auto-cdlc model admission. However, ordinary
`Start-ScheduledTask` remained **Queued** despite AC power and about
1% sampled CPU activity. To isolate the cause, two lightweight
automatically scheduled one-shot test tasks were registered for the
same clock time: the control task without idle conditions **ran and
wrote its local evidence**, while the otherwise equivalent
`RunOnlyIfIdle` task **did not start** at that time. This is real
proof that Windows can schedule unattended work but the idle gate
cannot be relied upon for our current worker. The old trigger only
responds to the OS entering its idle state, which may never transition
when the computer is already idle or background services keep it
outside that state.

Fix without surprising the user: change the registered worker to a
30-minute **time trigger**, but execute a separate Windows-local,
read-only `--scheduled-worker` admission gate first. Require AC, an
active console session, >=600 seconds without interactive input,
sampled system CPU <=20%, and no running Rocksmith/NoCableLauncher.
If any test fails or cannot be read, record only a sanitized local
SKIPPED heartbeat; do not run private musical analysis. Owner-disabled
Task Scheduler remains an absolute boundary. The previous direct
`--unattended-worker` diagnostic remains available. Require
exact-head CI/Windows Desktop, independent review and a real
automatic scheduled launch on Azathoth before claiming the fix
operational; do not confuse an overridden task, a disabled idle trigger,
or a skipped gate with verified musical correctness.

**Acceptance now verified (2026-11-21):** #783 merged at
`344a8f53f077b3321796b20be70222435ef292fe` after
2,390 passing Python tests, green Windows Desktop and pinned PSARC
CI, and clean independent review. The exact packaged Windows Desktop
artifact was installed under a SHA-specific user-local release
directory after checksum validation and isolated package smoke.
The enabled current-user limited task now has a **30-minute clock
trigger**, `RunOnlyIfIdle=False`, `WakeToRun=False`, and battery
start prohibition; all expensive work is guarded by the new
`--scheduled-worker` owner-safety check. **Windows autonomously
launched the actual registered task at 06:08:00 CST** without
`RunEx` or a manual request. Guard admitted at 12:08:01 UTC and
the locked worker completed at 12:08:02 UTC with current-build
evidence, last result **0**, and next scheduled event 06:38 CST.
This proves automated scheduling and worker execution, not musical
accuracy. All six recent timing checks remained `REVIEW_REQUIRED`
for insufficient evidence, and optional auto-cdlc models are
correctly blocked by missing packages/weights/RAM. The next music
engineering slice must make independent timing evidence usable rather
than repeat manual owner laptop tests.

**Slice D — unattended proof:** integrate validated candidates with
the #612 private Windows worker and #693 corpus differential tests,
without uploading protected audio, charts or raw project files.
Do not promote any model or automated packaging implementation as
gameplay-ready solely because CI or package structural inspection passes.

Detailed source audit, implementation contract and next gates:
[auto-cdlc integration](docs/integrations/AUTO_CDLC_INTEGRATION.md).
Noncommercial madmom model licensing and third-party runtime version
differences must be evaluated before importing its audio pipeline.

## Charter automation track (#769)

**Owner-approved 2026-11-14:** evaluate and, if demonstrated reliable, integrate [Charter](https://github.com/Lordszynencja/Charter/wiki) as an **optional unattended Rocksmith authoring/validation/XML-export backend** as well as a second independent reference alongside EOF. The success measure is **better playable Rocksmith 2014 Bass, Lead, and Rhythm songs with less human operation**, not an editor dependency or feature count. Owner prefers automation of a mature existing application over recreating its authoring capabilities if objective evidence supports the shortcut.

**Next bounded milestone:** prove a pinned Charter release can reliably ingest a legal synthetic song/GP score, validate its chart, and emit usable Rocksmith XML under program control. Upstream v0.23.1 supports GUI path-open, but **headless batch export is not yet verified**. Evaluate an isolated Java adapter, then reliable unattended Windows UI automation if necessary; fail closed to the existing generator if neither passes. Do not add unverified CLI or production claims. Extend #414 mature-reference parity, #612 unattended Product Reality, and #693 private corpus differential tests. Require cross-engine evidence on first entrance/repeated phrase/beat phase, Bass+Lead+Rhythm, techniques and chords, with intentional pre-roll normalized only using independent evidence. Preserve canonical review/source authority and existing DLC Builder/PSARC packaging gates. Keep live Rocksmith and private songs untouched.

**Tracking:** [issue #769](https://github.com/jweter/rocksmith-cdlc-generator/issues/769); [integration contract](docs/integrations/CHARTER_INTEGRATION.md). Schedule after higher-priority broken/merge-ready work, beginning with small format/CLI feasibility tests rather than a broad UI fork. No programmatic Charter execution is implemented by this roadmap update.


## North-star workflow

```text
Launch Windows app
  → choose local recording + complete score
  → review rights/provenance
  → confirm Bass / Lead / Rhythm mappings
  → analyze recording + fan out score tracks
  → align once
  → review/correct one shared timing model
  → generate three arrangement drafts
  → review notes/chords/fingering/techniques
  → validate
  → metadata / cover / tones
  → Rocksmith XML + DLC Builder handoff
  → build + verify PSARC
  → manual installation
```

The north-star workflow now has a second supported source path for practice material: **Printed Notation/TAB → reviewed structured score → generated practice clock/audio → Rocksmith arrangement**, with no commercial backing recording required. The full design is maintained in `docs/printed-notation-tab-practice-mode.md`.

## Governing rules

1. Build the Windows product continuously. Defects are recorded as GitHub Issues and do not hijack the roadmap unless they block the normal desktop path, cause reproducible wrong output/data loss, or violate a hard safety boundary.
2. Source media and registered score bytes are immutable identities.
3. One complete score is a project-level musical source, not three independent imports.
4. Bass, Lead, and Rhythm inherit one reviewed score-to-recording timing model whenever the shared-score workflow is used.
5. Human confirmation remains required for uncertain rights/provenance, source mappings, timing acceptance, fingering/playability, tone acceptance, and package readiness.
6. Never invent unresolved guitar string/fret positions or silently turn confidence into authority.
7. Never download/rip streaming-reference media.
8. Never modify the live Rocksmith installation or NoCableLauncher.
9. Never commit commercial audio, private packages, CFSM exports, Ubisoft-derived content, generated private project data, or commercial notation-book page images.
10. Packaging remains validation-gated.
11. Passing CI proves the contracts that are tested; it does not by itself prove that the desktop product is usable, responsive, understandable, or efficient for real authoring work.
12. Every claimed capability must be wired through the real product path. Avoid placeholder architecture, fake integrations, unused services, dead dependencies, and documentation claims that exceed demonstrated behavior.
13. Prefer the smallest architecture and dependency set that solves the current product problem. New backends, services, frameworks, dependencies, abstractions, or AI components require a concrete product need and a measurable benefit.
14. Preserve explicit ownership of truth across source → review authority → generated draft → validation → export → package. A downstream artifact must never silently become authoritative when its upstream identity or review authority is stale.
15. As the desktop grows, test the interactive product as well as the deterministic engine: selection, playback synchronization, canvas rendering, editing workflows, blocked-state explanations, and representative end-to-end user actions.
16. Profile representative dense and full-length songs instead of assuming GUI performance. Optimize measured bottlenecks, especially playback-time rendering, large arrangement previews, waveform/timeline drawing, and review navigation.
17. Do not allow the Song Workspace inheritance chain to become an uncontrolled mega-window. Prefer composition/controllers when feature layering begins to make behavior difficult to isolate, test, or reason about.
18. Periodically run an adversarial AI-code audit for dead or duplicate code, unnecessary dependencies, fake wiring, security mistakes, untested interactive behavior, accidental complexity, and capability claims unsupported by real execution.
19. Periodically sweep the repository Issues tab as a deliberate reliability stream. Fix safety/correctness blockers immediately, prioritize high-value normal-path usability/reliability issues alongside roadmap work, and avoid either extreme of ignoring the backlog or letting low-value issues halt product progress.
20. Every open product issue must have an explicit roadmap disposition: current milestone, next hardening milestone, standing engineering practice, later capability expansion, or intentionally deferred. The roadmap should reference issue numbers directly so scheduled development can select them instead of allowing the Issues tab to become a disconnected backlog.
21. Multiple notation/tab/reference candidates, when supported later, remain independent evidence identities. Reconciliation may rank or derive a consensus draft, but must preserve provenance, disagreement, human-review authority, and stale-state invalidation.
22. **Mature-reference-first rule (#414):** before inventing or materially changing deterministic Guitar Pro/Rocksmith authoring behavior, inspect Editor on Fire (EOF) or the relevant mature Rocksmith toolchain implementation first. Prefer tested parity with proven behavior, port/adapt license-compatible code when useful, and document intentional divergence. EOF parity is a correctness floor, not a requirement to copy its legacy GUI or mutable editor architecture.
23. Printed-notation recognition is evidence extraction, not authority by default. Keep original local page images immutable, preserve image-region provenance, expose recognition confidence, require review for material ambiguity, and never allow a vision/OMR guess to silently override explicit rests, string/fret choices, rhythms, repeats, or techniques.
24. In notation-practice projects, the authoritative tempo/measure map drives the Rocksmith note highway, click track, count-in, subdivisions, loops, and generated accompaniment. These outputs must share one clock so drift cannot be introduced by independent timing models.
25. Generated practice backing should be deterministic and derived from the reviewed structured score where practical. It is a practice aid, not an attempt to clone or redistribute the original commercial recording.
26. **Private-library regression rule (#693):** the user's installed Rocksmith library may be copied into a separate private local mirror and used as a real-world regression/reference corpus, but the live game library remains read-only and commercial audio, official/private PSARC packages, CFSM exports, extracted Ubisoft-derived content, and other restricted source bytes must never enter Git or public CI artifacts. Only sanitized derived evidence may be written back remotely.
27. A known-good Rocksmith arrangement is reference evidence, not automatic universal ground truth. Official material, user-trusted CDLC, and unverified custom content must retain explicit trust tiers, and comparison logic must distinguish required musical/timing agreement from legitimate alternate fretboard/authoring choices.

## Product Reality Gate

Feature count is not the product metric. At regular milestones, and before an installable release can be considered ready, run a real lawful song/score case through the packaged Windows application and evaluate the complete user workflow.

The Product Reality Gate must verify or measure:

- launch/open-project reliability on the packaged Windows build;
- recording + complete-score intake and Bass/Lead/Rhythm mapping through the GUI;
- timing review, arrangement navigation, direct event selection, and accepted edits through normal desktop controls;
- playback synchronization and correctness after repeated timing/position/technique edits;
- clarity of stale/blocked states and whether a user can understand what action is required next;
- responsiveness on representative dense/full-length material, including CPU/memory behavior and interaction latency;
- whether normal work can be completed without PowerShell or hidden manual repair steps;
- number and type of human corrections required for Bass, Lead, and Rhythm;
- actual human editing time, recorded during the correction session rather than estimated afterward;
- editing minutes per finished minute as the primary end-user productivity metric;
- successful validation, export, DLC Builder handoff, returned PSARC registration/verification, and manual installation readiness when those stages are in current product scope.

A roadmap milestone may be technically complete while still failing the Product Reality Gate. Product-reality failures become prioritized engineering evidence rather than being dismissed because unit tests pass.

The benchmark corpus and Product Reality Gate complement each other: automated/synthetic benchmarks detect deterministic regressions, while real desktop sessions test whether the whole application is genuinely useful. The private installed-library corpus in #693 adds a third lane: broad real-world differential evidence from mature Rocksmith arrangements without turning the user into the routine detector.

## Completed product foundation

Already implemented and reusable:

- immutable local project/audio ingest and FFmpeg normalization;
- beat/tempo analysis and Bass transcription/mapping;
- Guitar Pro 3–5 and MusicXML complete-score intake;
- explicit Bass/Lead/Rhythm track confirmation;
- score fan-out and one shared score-to-recording timeline;
- reviewed timing with loop/slow playback, variable-tempo click, locked anchors, deterministic refit, and explicit promotion;
- Lead/Rhythm drafts inheriting current reviewed shared timing;
- validation/review artifacts and Rocksmith XML authoring;
- DLC Builder staging and PSARC registration/verification;
- packaged Windows desktop executable built in GitHub Actions;
- Song Workspace with project health, arrangement state, review queue, provenance summary, synchronized waveform/timeline, and playback;
- synchronized Bass/Lead/Rhythm score-event preview on the recording clock;
- review-item navigation and tuning-aware virtual fretboard;
- provenance-aware physical string/fret acceptance with Lead/Rhythm draft invalidation;
- direct arbitrary arrangement-event selection with ambiguity-preserving chord-note choice;
- provenance-aware onset/duration acceptance with recording-clock preview overlays and Lead/Rhythm regeneration;
- provenance-aware technique acceptance with preview overlays and Lead/Rhythm regeneration;
- atomic whole-chord Lead/Rhythm fingering acceptance using the existing reviewed-position authority;
- provenance-aware reviewed Lead/Rhythm chord identity with explicit source-event membership and draft staleness binding;
- transactional provenance-aware undo/redo across accepted arrangement review layers with exact restoration and stale-authority refusal.

No unresolved/unverified physical guitar position may pass silently into export.

## Current milestone — Product Reality Gate v1

Before feature accumulation outruns product validation, exercise one representative lawful development song through the packaged Windows application and record a baseline Product Reality report.

### Measurement infrastructure

Provide a separate project-bound Product Reality recorder rather than adding more Song Workspace inheritance. It may record workflow evidence but must own no musical authority.

The recorder should capture:

- packaged build/artifact identity supplied by the tester;
- registered recording/score identity without copying media into reports;
- manually measured workflow stage durations;
- explicit marking of intervals that count as human editing time;
- Bass/Lead/Rhythm correction counts by timing, position, technique, chord/fingering, chord identity, and other work;
- usability/performance observations and whether CLI/PowerShell was required as a workaround;
- explicit final PASS/FAIL plus reason;
- a local JSON evidence record and human-readable Markdown summary;
- editing minutes per finished minute computed from measured editing intervals and recording duration.

Generated Product Reality reports remain local/private project data and must be gitignored.

### Required v1 evidence run

- one reproducible end-to-end session record using a real lawful song + complete structured score;
- timing for major workflow stages and total editing minutes per finished minute;
- Bass/Lead/Rhythm correction counts grouped by timing, position, technique, chord/fingering, and other review work;
- notes on confusing UI states, required workarounds, and any step that still requires CLI/PowerShell;
- responsiveness observations for playback, waveform/timeline drawing, arrangement preview, direct selection, repeated editing, and undo/redo;
- targeted follow-up issues for any normal-path usability, correctness, or performance defect found;
- an explicit pass/fail statement against the current Product Reality Gate, without redefining success after seeing the result.

This milestone is evidence-gathering, not a broad rewrite. Fix normal-path blockers, reproducible wrong output/data loss, and severe responsiveness problems immediately; record lower-severity findings for deliberate follow-up.

After the first Product Reality run, perform an Issues-tab sweep using the new evidence as one prioritization input: close obsolete/duplicate items, repair high-severity correctness/safety defects first, then select the highest-value usability/reliability issues that can be fixed without abandoning forward roadmap progress.

### Roadmap-linked issue queue

The currently open Rocksmith issues are part of the roadmap, not a separate unowned backlog. Scheduled and manual development should keep this queue synchronized with live GitHub state.

1. **#304 — Audit and fix current Product Reality defects before expanding scope.** This is the active defect-remediation umbrella for the current milestone. Reproduce normal-path failures from packaged-app testing, fix blockers and stale/incorrect authority first, add regression protection, and create focused child issues where needed. Do not close the Product Reality milestone while material #304 defects remain unresolved.
2. **#305 — Upgrade the Windows desktop UI to a polished authoring workspace.** Begin after or alongside the evidence-driven #304 remediation pass once the major functional defects are known. Treat this as the first major slice of the following authoring-hardening milestone: audit the running UI, establish a small reusable design system, then improve the primary workflow without weakening provenance, review, or validation gates.
3. **#193 — Track recurring defect patterns and root-cause fixes.** This is a standing engineering-memory obligation across every milestone. Recurring failures discovered through #304, #305, CI, or later Product Reality runs must be cross-linked here with root cause, prevention pattern, and regression coverage rather than repeatedly patched as isolated symptoms.
4. **#414 — Establish EOF reference, parity, and code-reuse program.** This is a standing engineering/reference program that begins immediately in parallel with Product Reality work. Audit mature EOF and Rocksmith-toolkit behavior before inventing deterministic authoring rules, maintain the parity matrix/fork inventory, port or adapt proven license-compatible behavior in small regression-protected slices, and use same-input differential testing where practical. It must accelerate current correctness work without blocking packaged Product Reality verification.
5. **#416 — Port EOF Rocksmith validation rule pack.** V1 is complete via PR #417: hard fret limits and actionable bend/slide/fingering/FHP diagnostics now feed the existing Bass/Lead/Rhythm validation architecture. Follow-on #414 slices should continue note-duration/tie/gap parity, replace lossiness warnings with structured support, then add playability, COUNT/END, phrase/section, XML and downstream validation rules only after their reference semantics are traced and tested.
6. **#391 — Compare multiple score/tab candidates and reconcile them against the recording.** Keep this under Later capability expansion until the single-score desktop workflow is stable. The capability should rank multiple structured/unstructured candidates globally and by section, surface disagreement, preserve source provenance, support a derived consensus draft, and allow explicit human verification from lawful private reference material. See `docs/multi-source-score-reconciliation.md`.
7. **#46 — Automate Apple Music metadata enrichment for benchmark candidates.** Keep this explicitly scheduled under Later capability expansion. It may proceed only after the normal Windows authoring/build flow is complete enough that metadata enrichment cannot displace core usability/reliability work. Apple Music remains an optional pluggable metadata source, never an audio source or hard runtime/build dependency.
8. **Printed Notation/TAB Practice Mode — roadmap expansion.** After the current desktop/product-reality work is stable enough to absorb a new intake path, implement the staged capability defined in `docs/printed-notation-tab-practice-mode.md`: photograph/scan → recognition/review → deterministic practice clock → click/count-in/subdivisions → optional generated accompaniment → Rocksmith arrangement. The first acceptance slice is one clear bass-TAB page, 4–8 measures, with a playable Rocksmith practice PSARC and no commercial backing recording.
9. **#693 — Build a private Rocksmith library regression corpus and unattended differential lane.** Treat this as a standing verification program supporting the current Product Reality automation objective. First build a safe hashed private mirror/inventory and one Tier A official Bass/Lead/Rhythm differential case; then expand representative corpus breadth incrementally. Keep all raw/restricted library bytes local and publish only sanitized derived evidence. See `docs/private-rocksmith-library-regression-corpus.md`.

When new issues are opened, assign each one to a roadmap disposition in the same planning cycle. Normal-path blockers and correctness/safety defects can move ahead of later feature work; optional integrations remain behind desktop-product completion unless they become necessary to satisfy a measured Product Reality need.

## Standing program — EOF reference, parity, and reuse (#414)

EOF and adjacent Rocksmith tooling are now explicit inputs to the development process rather than emergency references used only after a defect appears.

Durable program documents:

- `docs/eof-reference-parity-program.md`
- `docs/eof-subsystem-parity-matrix.md`
- `docs/eof-upstream-fork-inventory.md`
- `docs/eof-automated-comparison.md`
- `docs/eof-rocksmith-validation-rule-pack.md`
- `THIRD_PARTY_NOTICES.md`

The primary current EOF reference is `raynebc/editor-on-fire`. Forks are promoted only when commit/branch comparison proves useful divergence. The repository named `xmist001/editor-on-fire-automated` is currently classified as a historical May-2026 snapshot of primary EOF, not a separate automation implementation. The Rocksmith Custom Song Toolkit ecosystem is an adjacent reference for XML/SNG/package/DDC semantics subject to its own license audit.

The first concrete adoption slice, **#416 / PR #417: EOF-derived Rocksmith validation rule pack v1**, is merged. It converts mature authoring checks into machine-readable `ReviewItem` findings without copying EOF's GUI or fabricating missing musical intent. The next adoption lane applies the same mature-reference discipline to exact ties, note durations, required gaps and sustain endpoints.

Execution order:

1. EOF-derived Rocksmith validation rule pack and diagnostic coverage across Bass/Lead/Rhythm.
2. GP import + symbolic beat/timing semantics.
3. note duration/gap/sustain behavior.
4. repeats/ties/alternate endings/triplet feel.
5. structured bends/slides/techniques so current lossless-detail warnings can be retired legitimately.
6. chord/fingering/FHP/handshape behavior and explainable playability diagnostics.
7. phrases/sections/Rocksmith events, including COUNT/END structure where applicable.
8. Rocksmith XML validation/export.
9. toolkit/DDC/SNG/package semantics.
10. safe self-repair and automation improvements beyond the mature reference baseline.

For each subsystem, record the mature behavior, our corresponding implementation, parity state, reuse decision, licensing/provenance when code is adopted, and regression protection. Same-input semantic differential tests are preferred over intuition.

This program does **not** authorize a big-bang rewrite or an EOF runtime dependency by default. Port the smallest proven behavior needed, preserve this project's stronger authority/provenance/review model, and measure Product Reality impact.

## Standing program — Private installed-library regression corpus (#693)

**Local execution status (2026-11-11):** a verified private corpus now exists outside Git and outside the live Rocksmith/music folders, using immutable copies of both the user's installed packages and personal audio/project materials (320/320 matching source/copy hashes; 26/26 sampled PSARC file headers). This completes only a **local inventory/copy smoke**, not a proven differential lane or playable CDLC. The merged #695 implementation supplied an inventory/mirror foundation. The remaining dependency chain is **verified Tier A Bass/Lead/Rhythm reference → pinned PSARC bridge decoding → importer-fidelity tests and independent audio/score generation comparison → phase/note/chord mutation proof → sanitized exact-head unattended report → real-song packaging and owner-operated in-game Product Reality**. Do not confuse reference-fed import fidelity with independently generated musical accuracy. #693 remains open for its full acceptance criteria. See [2026-11-11 private local evidence and handoff](docs/private-rocksmith-corpus-local-handoff-2026-11-11.md). All private media, extracted assets, original paths and manifests remain off GitHub.


The user's existing Rocksmith library is now an explicit private verification asset. It should be copied into a separate read-only/hash-verified local mirror and used by the unattended Windows worker to compare generator output against mature real-world arrangements without requiring repeated manual inspection.

Durable specification:

- `docs/private-rocksmith-library-regression-corpus.md`

Reference trust tiers are mandatory:

- **Tier A:** official Rocksmith arrangements;
- **Tier B:** explicitly user-trusted high-quality CDLC;
- **Tier C:** unverified installed content used for compatibility/stress evidence only unless promoted.

The first implementation slice is deliberately bounded:

1. discover/configure the live Rocksmith DLC/library location;
2. create/refresh a private hashed mirror outside both Git and the live game directory;
3. inventory packages and preserve immutable package identity;
4. classify at least official versus custom content, with explicit trust tier;
5. choose one Tier A song with Bass + Lead + Rhythm;
6. extract a private normalized reference for timing/phase, arrangement presence, and pitch/chord identity;
7. run the same generator output through a differential report;
8. prove deliberate one-beat/one-measure phase errors and note/chord mutations are detected;
9. emit sanitized evidence bound to exact Git/build/tool identities;
10. run unattended on the approved Windows worker.

After that proof, expand coverage across representative tunings, bass/lead/rhythm styles, techniques, tempo behavior, sparse/dense songs, and full-song drift checks. A private corpus failure should be reduced into a safe synthetic/public regression fixture whenever practical.

This program must **not** turn copyrighted/restricted library content into public test fixtures, GitHub artifacts, or remote uploads. The laptop agent may make the local copies and perform the analysis; remote systems receive only sanitized derived evidence unless a future explicit rights/privacy decision authorizes something else.

The purpose is not to force exact note-for-note identity where multiple valid authoring choices exist. Timing phase, drift, pitch identity, tuning, arrangement presence, and structural invariants can have strict contracts; string/fret, techniques, sustain, phrases, and other authoring choices require equivalence/tolerance rules appropriate to the comparison.

## Following milestone — Evidence-driven authoring hardening

Use Product Reality Gate evidence and the current GitHub issue backlog rather than speculation to choose the highest-value fixes. #304 remediation findings and #305 are explicit inputs to this milestone, #193 remains active as the defect-memory layer, and #414 remains active as the mature-reference/parity layer. Likely areas include:

- complete the bounded Product Reality defect fixes identified under #304;
- execute #305 in evidence-driven slices: UI audit → design-system foundation → highest-value workflow surfaces → regression/smoke coverage;
- use #414 audits to avoid reinventing mature Guitar Pro/Rocksmith authoring behavior during correctness fixes;
- use #416's validation-rule-pack findings to prioritize structured technique, fingering/FHP and song-structure work by real warning frequency rather than guesswork;
- confidence/provenance and source-disagreement visualization;
- deliberate integration of reviewed event timing/position/technique overlays into the separate Bass authoring path;
- targeted Song Workspace composition/controller extraction where the inheritance chain demonstrably impedes testing or maintenance;
- targeted canvas/playback rendering optimization for measured dense-song bottlenecks;
- GUI interaction tests for the highest-risk normal user paths;
- high-value open issues whose impact is confirmed by normal-path use or correctness/safety analysis.

Do not perform a broad UI rewrite without measured product evidence. #305 should be delivered incrementally so visual polish and interaction changes remain reviewable and cannot mask functional defects.

## Following milestone — Complete desktop build flow

Bring the remaining end-to-end engine workflow into the GUI:

- three-arrangement validation dashboard;
- metadata and cover art;
- tones and tone regions;
- Rocksmith XML export;
- DLC Builder discovery/project preparation/launch;
- package staging and readiness view;
- returned PSARC registration and integrity verification;
- tool and audio-device diagnostics.

Normal use should not require PowerShell.

## Following milestone — Installable release

- stable versioning;
- branded icon/application metadata;
- GitHub release artifacts;
- installer or equivalently simple Windows distribution;
- first-launch dependency/tool diagnostics;
- user-settings/project migration and recovery behavior;
- optional safe update notification;
- Product Reality Gate passed on representative lawful material with no unresolved normal-path blocker or severe responsiveness defect.

## Later capability expansion

Important, but not allowed to displace completion of the desktop workflow:

- stronger audio-only transcription for songs without structured scores;
- additional score formats through safe adapters;
- richer technique detection;
- dynamic difficulty controls informed by #414's toolkit/DDC audit rather than invented without a mature reference model;
- section/phrase inference informed by EOF parity work where applicable;
- tone-region detection and Rocksmith device mapping;
- improved source reconciliation;
- **Printed Notation/TAB Practice Mode:** import a photograph or scan of guitar/bass notation or TAB; correct image perspective; recognize measures, rhythms, rests, string/fret positions, chords, repeats and techniques; cross-check TAB against standard notation; review low-confidence regions; promote a structured score; derive a deterministic tempo/measure clock; generate a count-in, accented click track, optional subdivisions, tempo-scaled practice variants, measure loops and optional deterministic backing accompaniment; then produce Bass/Lead/Rhythm Rocksmith arrangements without requiring a commercial recording. Full roadmap: `docs/printed-notation-tab-practice-mode.md`.
- **#391 multi-source score/tab/reference reconciliation:** register multiple candidates, align and score each against the same recording, rank globally and by section, navigate disagreement regions, derive a provenance-preserving consensus draft, and support explicit human verification from lawful private reference material; keep commercial score-book images/private page photographs local and out of Git; see `docs/multi-source-score-reconciliation.md`;
- batch/project-library tools;
- expanded benchmark suite and recurring real correction-time measurement, including gradual expansion of #693's private installed-library corpus after its first Tier A unattended slice is proven;
- **#46 Apple Music metadata enrichment for benchmark candidates through an optional pluggable metadata provider; cache only redistributable metadata/provenance and never audio;**
- optional local AI assistance only where it measurably reduces editing time without weakening provenance or human gates.

### Planned roadmap track — Printed Notation/TAB Practice Mode

This is a formal product track, not a speculative note. Its complete specification is `docs/printed-notation-tab-practice-mode.md`.

The intended end-user workflow is:

```text
Take or import a clear picture of a notation/TAB page
  → app checks image quality and corrects perspective
  → app recognizes systems, measures, notes, rests, rhythms, TAB strings/frets, chords and techniques
  → user reviews only highlighted uncertainties
  → app promotes the reviewed page(s) to the canonical structured score
  → app creates the tempo/measure map
  → user chooses practice tempo, count-in, click/subdivision and backing mode
  → app generates synchronized practice audio
  → app generates the Rocksmith Bass / Lead / Rhythm arrangement(s)
  → validate → package → play
```

The first proof of concept is intentionally bounded: **one clear photographed bass-TAB page → 4–8 consecutive measures → reviewed structured events → 2-measure count-in + click → optional simple generated drums/harmonic backing → playable Rocksmith bass practice arrangement without the original commercial backing track.**

Practice audio modes should progress from deterministic and testable to richer only when useful:

1. click only;
2. click + simple generated drums;
3. click + harmonic backing derived from recognized chords/key evidence;
4. optional synthesized target-part guide for recognition checking;
5. combined practice band with independently muteable layers.

The backing engine should initially use deterministic MIDI/synthesis/soundfont-style rendering so the audio is reproducible and locked to the same measure clock as the note highway. Generative audio should not be required for the feature and may be evaluated later only if it improves practice value without sacrificing timing, provenance, reproducibility, local-first operation, or legal clarity.

Measure-based practice is a core requirement. The user should eventually be able to request, for example, **measures 41–48, 70% tempo, two-measure count-in, eighth-note subdivision, drums + chords**, and receive a perfectly synchronized loop/practice arrangement derived from the same canonical score.

Printed rests are explicit timing evidence. Recognition and export must prevent false notes or sustains from crossing regions that the book says are silent. This requirement directly reinforces the same timing/sustain correctness work already active in the normal score workflow.

Full-song support follows after the single-page pipeline proves accurate: multi-page ordering, missing/duplicate page detection, page-break continuity, measure numbering, repeats, codas, segnos, first/second endings, tempo/time-signature changes, Bass/Lead/Rhythm part mapping, and complete-song Rocksmith practice packaging.

Commercial notation page images remain local/private and must never be committed to the public repository. Test fixtures must be synthetic, original, public-domain, or otherwise redistributable.

## Issue policy

When development or Codex review finds an error:

- create/update a GitHub Issue with reproduction context and expected fix direction;
- add or update that issue's explicit roadmap disposition so it cannot become an orphaned backlog item;
- continue the active product milestone by default;
- interrupt immediately for normal-path blockers, reproducible wrong output/data loss, hard safety violations, or severe Product Reality regressions in usability/responsiveness;
- at Product Reality and major milestone boundaries, review the full open Issues tab rather than only newly created issues;
- close or consolidate obsolete/duplicate issues, confirm reproduction where practical, and rank remaining work by safety/correctness, normal-path user impact, frequency, and effort/value;
- deliberately fix a bounded set of highest-value backlog items while continuing roadmap progress instead of allowing the backlog either to stagnate or to consume the entire roadmap;
- cross-link recurring defect classes to #193 and record the root-cause prevention pattern plus regression coverage;
- for deterministic Guitar Pro/Rocksmith authoring defects, cross-check #414's mature references before inventing a fix and record any newly discovered parity gap;
- record lower-value defects for later reliability/hardening passes.

## Success criteria

The project succeeds when a normal Windows user can launch the app, provide a song and score, make the few decisions automation should not make, review/correct Bass + Lead + Rhythm inside the application, and produce a valid Rocksmith CDLC package with materially less authoring effort than a manual workflow.

A second successful product path is now explicit: a user can photograph or scan a guitar/bass notation/TAB page, review a small number of uncertain recognition decisions, choose practice tempo/audio options, and generate a synchronized Rocksmith practice arrangement with count-in, click track and optional generated backing accompaniment without needing the original commercial recording.

Success must be demonstrated, not inferred from feature count or CI alone. Representative Product Reality sessions should show that the packaged desktop path is understandable and responsive and that measured editing minutes per finished minute improve meaningfully over the manual baseline.

Issue #414 adds an additional engineering success condition: mature deterministic authoring knowledge should be preserved rather than repeatedly rediscovered. Over time, the generator should match or deliberately improve the relevant EOF/Rocksmith reference behavior while automating substantially more of the workflow. Issue #416 makes that measurable by converting mature Rocksmith authoring checks into explicit pipeline diagnostics and, over time, safe deterministic prevention/self-repair where possible.

Issue #693 adds a further verification success condition: the private installed Rocksmith library should become a reproducible unattended real-world differential corpus, with raw restricted content remaining local and sanitized evidence preventing deterministic musical/timing regressions from being rediscovered manually.