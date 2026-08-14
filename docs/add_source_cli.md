# Unified `add-source` workflow

`cdlc add-source` is the preferred local intake entry point. It classifies the supplied file using the broad source registry, preserves the rights/provenance review state, and dispatches to an existing importer only when a deterministic adapter exists.

Examples:

```text
cdlc add-source song.flac --title "Song" --artist "Artist" --rights-class user_owned_local
cdlc add-source bass.mid --project projects/artist-song --instrument bass
cdlc add-source rhythm.gp5 --project projects/artist-song --instrument rhythm --track-index 2
cdlc add-source score.mxl --project projects/artist-song --instrument lead --part-index 1
cdlc add-source selected-custom.psarc --project projects/artist-song --instrument bass
```

Recognized audio creates a new project through the existing immutable audio-ingest path. MIDI, GP3/4/5, MusicXML/XML/MXL, and deliberately selected PSARC files route to their existing importers. Recognized future formats such as GPX, modern GP, PowerTab, TuxGuitar, TablEdit, and ABC return `queued` instead of being rejected or guessed at.

For sources attached to a project, `add-source` writes a hash-backed metadata receipt beneath `PROJECT/sources/intake/`. The receipt records the recognized format, route decision, source SHA-256, rights class, review state, and optional license note without copying additional source material into the repository. Default `projects/` remains gitignored.

`unknown` rights remain admissible for private local processing and are reported as requiring human rights/provenance review. A stronger rights classification can be supplied when the user knows the source is user-owned local material, a licensed download, Creative Commons, public domain, or self-recorded. These labels do not imply benchmark acceptance or redistribution rights.

Streaming/video references are intentionally excluded from `add-source`: reference URLs belong to discovery/version-identification workflows and are never converted into local bytes by this command.

The legacy format-specific commands remain available for advanced or scripted workflows. `add-source` is a routing facade over those same safe implementations rather than a second importer stack.
