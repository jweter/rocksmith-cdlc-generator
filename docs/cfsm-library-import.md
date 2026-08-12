# CFSM library metadata import

The generator should learn what is already in a user's Rocksmith library without scanning, copying, moving, renaming, or editing live Rocksmith files.

## Recommended source

Use a **JSON export from CustomsForge Song Manager (CFSM)**. In CFSM, open Song Manager, let the library scan finish, make the columns you want exported visible, then export the grid as JSON.

Recommended visible columns:

- Artist
- Song Title / Title
- Arrangements
- Tuning

If official DLC should be represented in the same catalog, enable CFSM's option to include ODLC before exporting.

The resulting JSON stays local/private. Do not commit a real personal library export to Git.

## Supported real CFSM shape

Current CFSM exports may use the top-level `dgvSongsMaster` collection with fields such as `colArtist`, `colTitle`, `colArrangements`, `colTunings`, `colRepairStatus`, and `colTagged`. The loader also accepts the earlier/common aliases documented by the library matcher.

Only artist/title, arrangement/tuning, and library-kind metadata are projected into the checker. Local `.psarc` paths that may exist in the CFSM export are not returned or copied.

## Read-only candidate checking

Use the CLI to check a proposed song against one local export:

```powershell
cdlc candidate-check `
  --catalog "C:\path\to\SongsMasterGrid.json" `
  --artist "Lamb of God" `
  --title "Laid to Rest"
```

The command prints JSON so the same result can be consumed later by the desktop UI or benchmark tooling. The result includes:

- `match_type`: `exact`, `normalized`, `ambiguous_exact`, `ambiguous_normalized`, or `none`;
- matching catalog entries with arrangements, tunings, and `library_kind`;
- same-artist entries as review context;
- the local catalog path, SHA-256, and filesystem modification timestamp.

Matching deliberately remains conservative:

1. case-insensitive exact artist + title;
2. deterministic normalized artist + title (case, punctuation, and diacritic normalization only);
3. otherwise no match, while same-artist songs are returned as review context.

There is no fuzzy similarity threshold and no automatic "probably the same song" decision. Multiple exact/normalized matches remain explicitly ambiguous for human review.

Every result records the local export path, SHA-256, and filesystem modification timestamp so later benchmark decisions can state exactly which catalog was checked.

## Safety boundary

This feature reads metadata only. It must never:

- modify the CFSM export;
- modify the live Rocksmith installation;
- modify NoCableLauncher;
- copy or commit commercial `.psarc`/audio content;
- expose local `.psarc` paths through the projected result;
- treat an existing CDLC as ground truth automatically.

Personal CFSM exports and generated comparison reports should remain local/private and gitignored.
