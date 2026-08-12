# MusicXML Arrangement Import Manifest

The multi-arrangement Guitar Pro 8 / MusicXML workflow now leaves behind a durable project-level manifest after all explicitly selected arrangements import successfully.

Example:

```text
py -3.12 scripts/import_musicxml_arrangements.py PROJECT "C:\path\to\song.musicxml" --lead-part 1 --rhythm-part 2 --bass-part 3
```

The command still writes one normalized imported-source JSON file per arrangement. It also writes:

```text
PROJECT/sources/imported/musicxml-arrangements-<source-sha-prefix>.json
```

The manifest records:

- source filename and SHA-256;
- exact human-selected MusicXML part index and part id/name for each role;
- tuning and pitched-note count observed during inspection;
- project-relative path to each normalized imported arrangement JSON.

The manifest does **not** contain the absolute path to the operator's Guitar Pro or MusicXML library. The original score stays in place and is not copied into the project or repository.

This manifest is intended to become the stable arrangement entry point for Song Preview & Timing Editor work. It records human choices; it does not infer or approve arrangement roles.
