# Editor on Fire integration

Last reviewed: 2026-08-21

## Purpose

Editor on Fire (EOF) is an established rhythm-game chart editor with mature Guitar Pro and Rocksmith authoring behavior. For this project, EOF is valuable as an independent compatibility/reference oracle for Guitar Pro intake, tuning/string/fret interpretation, fret-hand-position behavior, and Rocksmith authoring semantics.

This integration is intentionally optional. EOF does not become authority over the Rocksmith CDLC Generator's project state.

## Implemented boundary

The bridge is implemented as `rocksmith_cdlc_generator.eof_bridge`, the `cdlc-eof` command, an optional **Open in EOF** control in the Windows Song Workspace, and the read-only `rocksmith_cdlc_generator.eof_compatibility` evidence comparator.

It can:

- discover a user-installed EOF executable from an explicit path, `ROCKSMITH_CDLC_EOF_EXE`, `EOF_EXE`, or `PATH`;
- resolve the project's immutable registered GP3/GP4/GP5 score through the existing verified score contract;
- launch that exact registered score in EOF using EOF's documented command-line Guitar Pro import path;
- print the verified command without launching EOF for diagnostics;
- expose launch readiness in Song Workspace and enable **Open in EOF** only when both a compatible verified score and a user-installed EOF executable are available;
- compare deterministic importer output against source-bound, independently reviewed EOF observations for tuning, string/fret coordinates, note timing, MIDI identity, and project-supported techniques;
- preserve every comparison discrepancy as read-only evidence without mutating imported or reviewed chart state.

It deliberately does **not**:

- download or install EOF;
- vendor EOF source or binaries;
- scan arbitrary user directories for executables;
- allow EOF to silently replace confirmed Bass/Lead/Rhythm source mappings;
- import EOF edits back into canonical project authority automatically;
- auto-correct tuning, positions, timing, techniques, or note identity from comparison evidence;
- bypass timing, fingering/playability, validation, or packaging gates.

## Configuration

Install EOF separately, then either put `eof.exe` on `PATH` or set:

```powershell
$env:ROCKSMITH_CDLC_EOF_EXE = "C:\Path\To\EOF\eof.exe"
```

`EOF_EXE` is also accepted as a compatibility alias.

## Usage

For the normal Windows workflow, open the project in Song Workspace. When the registered score is GP3/GP4/GP5 and EOF is discoverable, the **Editor on Fire reference** panel enables **Open in EOF**. If EOF is absent or the score is incompatible, the control stays disabled and explains why.

The CLI remains available for diagnostics and scripting:

```powershell
cdlc-eof "C:\Path\To\Rocksmith CDLC Projects\my-project"
```

Inspect the command without launching the external application:

```powershell
cdlc-eof "C:\Path\To\Rocksmith CDLC Projects\my-project" --show-command
```

An explicit executable path can be supplied when needed:

```powershell
cdlc-eof "C:\Path\To\project" --executable "C:\Tools\EOF\eof.exe"
```

## Deterministic compatibility fixture

`tests/fixtures/eof/synthetic-gp5-reference.json` is a synthetic, non-commercial reference fixture. It records a source hash, GP format, source-track identity, EOF reference version/note, tuning, and event-level timing/pitch/string/fret/technique observations. `compare_imported_source_to_eof_fixture()` compares that evidence against the project's deterministic `ImportedSource` model.

The fixture contract fails closed when the score hash or source-track identity is stale. Timing comparison uses an explicit tolerance, technique comparison is restricted to the project's supported technique vocabulary, and the report records mismatches without changing either side of the comparison. The synthetic fixture exists to make the compatibility machinery regression-testable without committing any commercial Guitar Pro content or private project evidence.

A future real-song compatibility observation may use the same schema only when the underlying score/evidence is lawful to retain in the intended location. Private or copyrighted project evidence remains outside Git.

## Authority and provenance

The registered score remains immutable project evidence. The bridge uses the existing score-contract verification before it launches EOF, so a stale, missing, tampered, or out-of-project score path is refused rather than opened.

EOF is a reference/oracle surface. Observations from EOF may justify a human correction or a code change, but launching EOF or producing a compatibility report never records a human acceptance decision and never promotes EOF state to canonical arrangement authority.

Structured EOF-comparison artifacts are review evidence with explicit provenance, not silent replacements for project state.

## Immediate Product Reality use

The current Product Reality case exposed Bass notes encoded as symbolic string 0 / fret 0 / MIDI 27 while the generated mapper had fallen back to E Standard with lowest open pitch MIDI 28. The Rocksmith generator now has direct evidence for the failure and a conservative reviewed-tuning recovery path awaiting packaged-app verification.

EOF gives this project a second mature implementation against which the same GP source can be inspected when importer/string-numbering/tuning semantics are questionable. The one-click Song Workspace bridge removes command-line friction from that comparison without changing authority, while the deterministic fixture gives future observed discrepancies a testable and provenance-aware representation.

## Next integration slices

1. Investigate EOF fret-hand-position and fingering validation behavior as reference material for the project's global fretboard-position optimizer.
2. Add a project-local structured comparison-report workflow for lawful/private observations, preserving every discrepancy as review evidence rather than auto-correcting canonical charts.
3. Extend compatibility coverage only where a discrepancy is independently reproducible and materially useful to Bass/Lead/Rhythm authoring.
4. Keep EOF optional and replaceable; normal project generation must continue to work when EOF is absent.

## Licensing and maintenance

The upstream Editor on Fire repository uses a permissive BSD-style three-clause license. This integration does not redistribute upstream source or binaries, which keeps the dependency boundary small and avoids adding a bundled third-party application to the Windows artifact.

Before any future redistribution or source reuse, re-review the exact upstream revision, notices, license obligations, maintenance implications, and whether direct reuse provides enough benefit over the external-adapter boundary.
