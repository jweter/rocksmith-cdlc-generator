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

## Read-only candidate checking

`rocksmith_cdlc_generator.candidate_check` consumes the exported JSON without modifying it. The loader accepts a top-level row array or a common named row container such as `SongsMasterGrid`, `songs`, `rows`, or `data`.

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
- treat an existing CDLC as ground truth automatically.

Personal CFSM exports and generated comparison reports should remain local/private and gitignored.
