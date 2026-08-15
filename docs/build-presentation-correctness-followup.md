# Build presentation correctness follow-up

This follow-up tightens the package-presentation boundary introduced by the desktop metadata and cover workflow.

## Owned files

The presentation feature owns only these private project-local cover destinations:

- `assets/cover.png`
- `assets/cover.jpg`
- `assets/cover.jpeg`

Replacing confirmed cover art may remove stale files from that exact set. It must never glob or delete other `cover.*` files because those may be user-managed license, source, attribution, or backup artifacts.

## CLI fallback and explicit override

`cdlc prepare-dlcbuilder PROJECT` may omit `--cover`. When album, year, or cover is omitted, the builder may use the human-confirmed project presentation for the missing values.

A caller that supplies all three package-presentation values (`--album`, `--year`, and `--cover`) is making a complete explicit override. That path must not load or validate saved presentation state first; malformed, missing, or tampered saved presentation data cannot block a deliberate complete override.

Partial overrides still load saved presentation state for missing values and therefore continue to fail closed if that authority is unreadable or its confirmed cover bytes no longer match.

## Safety boundary

These rules affect package presentation only. They do not approve or mutate source rights, score mappings, shared timing, notes, positions, fingering, techniques, chord identity, tone decisions, validation, PSARC readiness, the live Rocksmith installation, or NoCableLauncher. Commercial audio/DLC, private CFSM exports, Ubisoft-derived content, and generated private project data remain outside version control.
