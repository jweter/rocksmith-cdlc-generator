# Charter — unattended Rocksmith authoring integration plan

**Issue:** [#769](https://github.com/jweter/rocksmith-cdlc-generator/issues/769)  
**Status:** implementation authorized; capability feasibility NOT YET verified; no Charter runtime is currently wired into the Rocksmith generator.  
**Owner intent:** prioritize producing reliable, playable Rocksmith 2014 Bass + Lead + Rhythm packages with little/no repetitive user operation. It is acceptable—and preferable when objectively better—to automate mature authoring software rather than rebuild all its functionality.

## Upstream evidence reviewed (2026-11-14)

- Upstream: https://github.com/Lordszynencja/Charter and https://github.com/Lordszynencja/Charter/wiki
- Release checked: **0.23.1**, published 2026-11-12. Pin the precise installed artifact hash and upstream commit before running real acceptance; a tag/name is not enough.
- Root license: **BSD-3-Clause**, copyright (c) 2025 Lordszynencja. Bundled third-party subtrees (e.g. audio/DSP libraries) require an independent license and distribution review; **no Charter code is bundled in this planning change**.
- Java entry point `src/main/java/log/charter/CharterMain.java` (source blob SHA `4052d0838773abf705c73d1eca8e9999dffc2359`) checks the first argument for a path and calls `CharterContext.openProject(path)`. This proves path-open support **in its GUI** and does not prove a headless engine.
- `src/main/java/log/charter/services/data/files/SongFileHandler.java`: `save()` serializes `.rscp`, runs `chartValidator.validate()`, writes Rocksmith XML into the `RS XML` project directory. It is triggered via the editor's save workflow; discover/test a non-GUI invocation before calling it automated.
- `src/main/java/log/charter/services/data/validation/ChartValidator.java`: validates beat map and arrangement structures (including overlaps, FHP, handshapes, phrases and sections).
- `src/main/java/log/charter/io/gp/gp5/`, `.../gp/gp7/`, `.../rs/xml/`, `.../rsc/xml/`: candidate input/output and format reference sources for a bounded adapter.
- Caveat: Charter expects suitable Rocksmith lead-in before first beat; its validator flags a first beat before 10 s. Distinguish intentional count-in/leading-silence normalization from a **real two-measure score-to-audio phase failure**.

## Engineering strategy — use the program if it works

The first question is **Can we programmatically drive a pinned Charter build to produce and validate Rocksmith XML?** Answer it with an executable synthetic experiment before proposing a large new framework.

Preference order:

1. **Headless in-process adapter:** invoke proven isolated Charter project-import/validator/export classes from a small maintained Java entry point, without launching the interactive GUI, only if dependency and licensing review show this is safe. Return machine-readable diagnostics and exact inputs/outputs.
2. **Unattended Windows desktop adapter:** if there is no stable non-GUI path, use pinned Charter executable in an isolated desktop environment with a narrowly scoped, restartable UI automation driver. Confirm each control/result by program output/files; handle interruption, focus/window failures, timeouts and stale exports. Do not silently use stale files or disable security software.
3. **Reference-only fallback:** if both are unreliable, retain Charter as a secondary behavioral oracle while our own engine remains the production path. Do not add an unstable dependency to the product.

A GUI screenshot, process startup, or `project.rscp` file by itself is NOT evidence that valid Rocksmith XML was exported.

## Proposed local pipeline (not yet implemented)

```text
immutable lawful recording + full GP/structured score
    -> existing generator: analyze / sync / reviewed Bass + Lead + Rhythm
    -> staging workspace only (private, hash-bound, immutable inputs)
    -> optional pinned Charter authoring backend (validated capability)
    -> Charter-generated Rocksmith XML + validation diagnostics
    -> independent comparison with generator + EOF on shared recording clock
    -> fail closed on unreviewed/stale/ambiguous music
    -> existing DLC Builder / PSARC / private Product Reality gates
    -> game-ready staged artifact (never auto-install or publish)
```

Use the same source/recording provenance and shared reviewed timing authority for Bass, Lead and Rhythm. A Charter project must not change original source rights, the score-to-recording phase, or promoted fingering/technique authority without a project-owned review/reconciliation step.

### Execution and evidence contract

A future optional interface MAY expose `cdlc charter doctor`, `cdlc charter export` and `cdlc charter compare`. **These are proposed commands only; none exist as a result of this document.** Do not register a dead CLI command.

For every automatic run, record:
- generator commit/build SHA, Charter git commit and actual executable SHA-256, Java/runtime version, invocation and configuration identity;
- hashes of private input audio/GP/score and generated Charter/native/RS XML files, without publishing source bytes or private path names;
- selected Bass/Lead/Rhythm IDs; note/chord totals; first playable event times; beat/measure anchors and later checkpoints; warnings/errors; exact return status;
- `PASS` only for executed, current and verified assertions; `FAIL` for falsified deterministic checks; `REVIEW_REQUIRED` for unavailable tool, unsupported format, ambiguous alignment, unverified UI behavior, missing evidence or incomplete PSARC/game verification.

### Differential oracle acceptance

Use **synthetic media-safe fixtures first** and later private lawful reference songs on the existing unattended local worker.

- Absolute recording clock versus symbolic score clock is explicit and separately logged.
- No arbitrary fixed 2-bar/seconds correction. Repeated riffs cannot steal the first complete-score sync from the true entrance.
- Bass + Lead + Rhythm share approved alignment. Compare each role's beat times, note onset/duration, pitch, string/fret, chord/template composition, techniques, FHP, handshape, phrase/section and Rocksmith export semantics.
- Normalize only documented, verifiable intentional lead-in conventions. Alternate playable frettings are reviewed disagreements, not automatic timing failures.
- Charter and EOF agreeing is **not** sufficient ground truth; require an independent audio/score or licensed known-good oracle where possible.
- All deterministic checks belong to #612 and/or #693; no repeated human laptop measurement. Game compatibility and human musical quality are separate gates.

## Initial bounded deliverables

1. Probe availability, pinned release, Java requirements, baseline launch behavior and security/install implications on an isolated test worker.
2. Prove or falsify a programmatic import -> validate -> RS XML export using a short, legally shareable synthetic Bass/Lead/Rhythm fixture; capture stderr/exit code, export hashes, validator findings, and a repeatable run description.
3. If possible, add a provider adapter behind existing workflow; if not, record the exact blocker and evaluate safe Windows GUI automation, then fall back cleanly.
4. Add Charter-vs-EOF-vs-generator normalized XML/clock comparisons to the existing differential program and regression tests for #431/#455.
5. Advance end-to-end staging/PSARC validation only after prior gates are supported. An exported XML is not a verified playable song.

## Safety and repo-policy alignment

- No modifications to live Rocksmith installation or NoCableLauncher; no automatic installation/redistribution of song packages.
- No commercial recordings, private tabs, copyrighted images, source stems, local PSARC libraries, CFSM exports, or user profiles in repository or CI.
- No installation onto the owner's laptop or antivirus exclusions without explicit owner authorization.
- Charter is optional/replaceable, never the system of record for musical review. Keep EOF reference behavior, provenance, stale-state invalidation and fail-closed packaging.
- Before implementing major domain semantics, perform mature-reference inspections required by #414 and keep ADR/source-license evidence.
- Existing outstanding failed or mergeable PRs remain first priority under the autonomous development contract.

**Related:** [#414](https://github.com/jweter/rocksmith-cdlc-generator/issues/414), [#612](https://github.com/jweter/rocksmith-cdlc-generator/issues/612), [#693](https://github.com/jweter/rocksmith-cdlc-generator/issues/693), [#769](https://github.com/jweter/rocksmith-cdlc-generator/issues/769).  
**Cross-project inventory:** `jweter/knowledge-engine-core/docs/integrations/EXTERNAL_REPO_RESEARCH_LEDGER.md`.
