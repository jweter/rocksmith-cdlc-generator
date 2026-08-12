# Guitar Pro 8 → MusicXML workflow

## Purpose

Guitar Pro 8 native `.gp` files are not required to become a project dependency. For local scores the operator already owns, Guitar Pro can export MusicXML and the project can inspect/import that structured notation without copying the original score into the repository.

## Export from Guitar Pro 8

Open the score in Guitar Pro and use **File → Export → MusicXML**. Save the `.musicxml` file somewhere local. The file remains operator-owned local input; do not commit commercial or licensed score files to this repository.

## Inspect before import

From the repository root:

```text
py -3.12 scripts/inspect_musicxml.py "C:\path\to\song.musicxml"
```

The command prints each MusicXML part in source order with:

- zero-based part index;
- part name;
- pitched-note count;
- measure count;
- staff tuning when exported;
- Lead, Rhythm, and Bass heuristic scores.

Scores are hints only. Track names and tuning remain important, and ambiguous choices should be selected explicitly by the operator.

For machine-readable output:

```text
py -3.12 scripts/inspect_musicxml.py "C:\path\to\song.musicxml" --json
```

## Import the chosen arrangement

After creating a CDLC project, import a selected part explicitly:

```text
cdlc import-musicxml PROJECT --musicxml "C:\path\to\song.musicxml" --instrument lead --part-index 1
```

Use `rhythm` or `bass` for the other arrangement roles. A full Guitar Pro score may therefore feed several Rocksmith arrangements by importing different part indices from the same MusicXML export.

## Trust and review boundary

MusicXML is treated as structured symbolic evidence, not unquestioned truth. The importer preserves available timing, tempo, time signatures, tuning, note pitches, strings/frets, and supported techniques, while later alignment/reconciliation and human review remain responsible for validating the arrangement against the recording.

The inspection step is read-only. It does not modify Guitar Pro, the source file, Rocksmith, NoCableLauncher, audio drivers, or tone approval state.
