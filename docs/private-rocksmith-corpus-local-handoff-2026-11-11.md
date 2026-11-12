# Private Rocksmith library corpus — verified local evidence and implementation handoff (2026-11-11)

**Tracking:** [#693](https://github.com/jweter/rocksmith-cdlc-generator/issues/693), [canonical plan](../PROJECT_PLAN.md), [corpus specification](private-rocksmith-library-regression-corpus.md).  
**Evidence class:** local read-only inventory and copy verification only. **Not** a Product Reality, import-fidelity, or generated-song accuracy PASS.

## Owner intent and protection boundary

The owner confirmed that both the installed Rocksmith 2014 / CDLC library **and** local music collection may be used for this project and instructed: **"Make copies for the project so my original isn't ever compromised."**

Implement this strictly as a local, copy-only evaluation asset. The live Steam installation and music originals are read-only. Any private audio, package, charts, source paths and extracted data stay on the owner's laptop outside Git, GitHub CI/artifacts and cloud upload. Do not copy entire libraries indiscriminately or rewrite, delete, hardlink into test workspaces, move, patch, install over, or alter originals. Preserve hash verification and fail closed on mismatch. Avoid heavyweight work competing with Iron God's local model or a Rocksmith gameplay session.

The corpus is stored in a **private Documents directory outside the repository and game install**; its exact local absolute path is available through the authenticated local owner/worker, not recorded in public source control.

## Local state verified on 2026-11-11

| Collection | Source inventory | Private copies | Scope |
|---|---:|---:|---|
| Active Rocksmith PSARC packages | 1,960 | 26 | Deterministic representative sample; not a complete mirror |
| Backup Rocksmith PSARCs | 319 | 0 | Catalogued only |
| Personal music (iTunes and loose audio) | 270 | 270 | Local M4A and MP3 |
| Existing CDLC project source files | 24 | 24 | Selected audio, MIDI, Guitar Pro |
| **Total** | **2,573** | **320** | Approximately **2.939 GiB** copied |

- SHA-256 original-versus-copy comparison: **320/320 equal**, **0 reported copy failures**.
- Lightweight private copy-only PSARC signature check: **26/26** sampled headers begin with `PSAR`; this proves only a recognizable header, **not** full decoding or package validity.
- Local `ffprobe` and `dotnet` executables were present. The pinned PSARC bridge DLL was not built at the checkout path inspected.
- Local private files include `source-catalog.csv` (original paths), `copy-manifest.csv` (source/copy paths and checksums), `local-corpus-smoke.json`, and README. **Do not upload these private files unredacted.**
- Trust tiers have **not** been established. All unknown/custom content remains **Tier C** until independently identified; filename resemblance alone cannot promote to Tier A or B.
- No generator-to-reference comparison, real-song DLC Builder build, returned PSARC verification, or in-game load was performed by this inventory work.

These counts are a point-in-time evidence snapshot, not a continuously refreshed or guaranteed complete inventory of every possible drive/folder.

## How the project uses it

Separate the following lanes to prevent circular accuracy claims:

**Lane 1 — importer fidelity (reference in, reference out).** On a private copy only, verify that a supported PSARC/notation importer preserves recoverable beat grid, tempo, tuning, arrangement metadata, note timing/pitch and technique details. Feeding the official reference into an importer is useful for parser fidelity but **does not** validate independent note generation.

**Lane 2 — independent arrangement generation.** Select a recording and independently available lawful score/notation that match a genuine official **Tier A** reference arrangement (same edition, recording, tuning, instrument and arrangement version). Generate without supplying the reference PSARC/chart as input. Compare first playable event, beat/measure phase, cumulative drift, pitch sets, event recall/precision, structural invariants, and separate fret/string/technique-equivalence metrics. Never fail merely because two playable arrangements choose different valid fingerings.

**Lane 3 — private real-song packaging / Product Reality.** Generate and validate Rocksmith XML; use DLC Builder privately; verify the returned PSARC. After machine-checkable results pass, separately validate installation and gameplay in an **owner-controlled** test session. No automation should overwrite the live game, profile or DLC folders. Synthetic-only CI, PSAR header checks, and parser passes are not proof of in-game playability.

## Next bounded implementation / acceptance

1. Reconcile the merged **#695** inventory/mirror helper with this existing private corpus. Keep the path configurable and avoid redundant copies. Verify source immutability, incremental refresh, recoverability of partial copies, and hash-detected divergence.
2. Implement reliable Tier A official-package classification, rather than using filenames; select **one verified official Bass + Lead + Rhythm case**.
3. Build/validate the pinned .NET PSARC bridge with isolated private extraction and preserve normalized reference provenance.
4. Build first private differential comparator and test **deliberate one-beat and one-measure phase shifts plus note/chord mutations** (and later drift, rest crossings, tuning/arrangement omissions).
5. Record machine-readable `PASS`, `FAIL`, `REVIEW_REQUIRED`, or `ENVIRONMENT_FAILURE`, corpus snapshot hash, Git commit, build/tools versions, source hashes and sanitized metrics. Reduce private defects to publishable synthetic regression fixtures where possible.
6. Only after differential acceptance, run a lawful real-song export through XML → DLC Builder → PSARC verification; reserve in-game gameplay acceptance for the owner.

**Completion condition:** #693 remains open until a verified Tier A three-arrangement case, mutation-detecting unattended differential, exact-head evidence and all local-only privacy restrictions satisfy its full acceptance criteria. PR #695 merged only the mirror/inventory foundation.

## Ownership and coordination

- **ChatGPT:** verified the initial local private copy/inventory and PSAR header smoke; may supply sanitized local findings, not private content.
- **Claude Code:** non-overlapping repository implementation, bridge/comparator work and reviews under the existing Git/CI gates.
- **Iron God:** roadmap-derived planning and capability-appropriate execution only within authenticated owner Take the Wheel control and resource admission; the MCP mailbox is advisory, not execution approval.

Use GitHub issues/PRs for durable engineering progress and the shared advisory mailbox for brief handoffs. Avoid overlapping file ownership or duplicate work. Do not promote unverified assumptions into PASS.
