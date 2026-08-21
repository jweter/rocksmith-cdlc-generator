# Editor on Fire integration

Last reviewed: 2026-08-20

## Purpose

Editor on Fire (EOF) is an established rhythm-game chart editor with mature Guitar Pro and Rocksmith authoring behavior. For this project, EOF is valuable as an independent compatibility/reference oracle for Guitar Pro intake, tuning/string/fret interpretation, fret-hand-position behavior, and Rocksmith authoring semantics.

This integration is intentionally optional. EOF does not become authority over the Rocksmith CDLC Generator's project state.

## Implemented boundary

The initial bridge is implemented as `rocksmith_cdlc_generator.eof_bridge` plus the `cdlc-eof` command.

It can:

- discover a user-installed EOF executable from an explicit path, `ROCKSMITH_CDLC_EOF_EXE`, `EOF_EXE`, or `PATH`;
- resolve the project's immutable registered GP3/GP4/GP5 score through the existing verified score contract;
- launch that exact registered score in EOF using EOF's documented command-line Guitar Pro import path;
- print the verified command without launching EOF for diagnostics.

It deliberately does **not**:

- download or install EOF;
- vendor EOF source or binaries;
- scan arbitrary user directories for executables;
- allow EOF to silently replace confirmed Bass/Lead/Rhythm source mappings;
- import EOF edits back into canonical project authority automatically;
- bypass timing, fingering/playability, validation, or packaging gates.

## Configuration

Install EOF separately, then either put `eof.exe` on `PATH` or set:

```powershell
$env:ROCKSMITH_CDLC_EOF_EXE = "C:\Path\To\EOF\eof.exe"
```

`EOF_EXE` is also accepted as a compatibility alias.

## Usage

Open the project's registered GP3/GP4/GP5 score in EOF:

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

## Authority and provenance

The registered score remains immutable project evidence. The bridge uses the existing score-contract verification before it launches EOF, so a stale, missing, tampered, or out-of-project score path is refused rather than opened.

EOF is a reference/oracle surface. Observations from EOF may justify a human correction or a code change, but launching EOF never records a human decision and never promotes EOF state to canonical arrangement authority.

Future structured EOF-comparison artifacts must therefore be modeled as review evidence with explicit provenance, not as silent replacements for project state.

## Immediate Product Reality use

The current Product Reality case exposed Bass notes encoded as symbolic string 0 / fret 0 / MIDI 27 while the generated mapper had fallen back to E Standard with lowest open pitch MIDI 28. The Rocksmith generator now has direct evidence for the failure and is adding a conservative partial-tuning recovery rule.

EOF gives this project a second mature implementation against which the same GP source can be inspected when importer/string-numbering/tuning semantics are questionable. This reduces the chance of repeatedly debugging Rocksmith-specific behavior in isolation.

## Next integration slices

1. Add an obvious **Open in EOF** control to the Windows Song Workspace when a compatible registered GP score and EOF installation are available.
2. Build a deterministic compatibility fixture that compares our imported track tuning, string/fret coordinates, note timing, and supported techniques against independently reviewed EOF behavior.
3. Investigate EOF fret-hand-position and fingering validation behavior as reference material for the project's global fretboard-position optimizer.
4. Add a structured comparison report for discrepancies, preserving every discrepancy as review evidence rather than auto-correcting canonical charts.
5. Keep EOF optional and replaceable; normal project generation must continue to work when EOF is absent.

## Licensing and maintenance

The upstream Editor on Fire repository uses a permissive BSD-style three-clause license. This initial integration does not redistribute upstream source or binaries, which keeps the dependency boundary small and avoids adding a bundled third-party application to the Windows artifact.

Before any future redistribution or source reuse, re-review the exact upstream revision, notices, license obligations, maintenance implications, and whether direct reuse provides enough benefit over the external-adapter boundary.
