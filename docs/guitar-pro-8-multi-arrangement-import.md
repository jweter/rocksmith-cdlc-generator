# Guitar Pro 8 Multi-Arrangement Import

Use this after exporting a Guitar Pro 8 score as MusicXML and inspecting it with `scripts/inspect_musicxml.py`.

The inspection step gives the source-order part indexes. Human selection remains authoritative; the importer does not silently assign ambiguous parts.

Example inspection result might identify:

- part 1: lead/electric guitar candidate
- part 2: rhythm/reverse guitar candidate
- part 3: bass candidate

Import all selected arrangements into an existing CDLC project with one command:

```text
py -3.12 scripts/import_musicxml_arrangements.py PROJECT "C:\path\to\song.musicxml" --lead-part 1 --rhythm-part 2 --bass-part 3
```

Any subset is allowed. For example, Lead + Bass only:

```text
py -3.12 scripts/import_musicxml_arrangements.py PROJECT "C:\path\to\song.musicxml" --lead-part 1 --bass-part 3
```

The command:

- reads the local MusicXML file in place;
- verifies every selected part index exists before writing;
- rejects assigning one source part to multiple Rocksmith arrangement roles;
- rejects duplicate role selections;
- imports each role through the existing MusicXML importer;
- writes only normalized project JSON under `PROJECT/sources/imported/`;
- does not copy the original Guitar Pro or MusicXML source into the repository;
- does not modify Rocksmith, NoCableLauncher, audio drivers, or tone approval state.

After import, the arrangement JSON can feed the existing alignment and guitar/bass authoring workflows. Repeats and complex score-navigation directives still require reconciliation where the MusicXML importer reports warnings.
