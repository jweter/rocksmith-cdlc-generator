# ADR-038: Rocksmith tone manifest semantic adapter

## Status
Accepted

## Context

The private PSARC extraction bridge can expose JSON files from SHA-256-verified private package copies, but filename heuristics are not sufficient to populate the tone-reference library safely. The semantic adapter needs an explicit supported schema and must not guess when fields are absent or malformed.

The implementation is grounded in the pinned `rscustom/rocksmith-custom-song-toolkit` model at commit `2afa730c71cbacdee57dcf5cb6461f65eaf4f1e5`:

- `Manifest2014<T>` defines `Entries` as a nested dictionary containing `Attributes2014` records.
- `AttributesHeader2014` provides `ArtistName`, `SongName`, and `ArrangementName`.
- `Attributes2014` provides `ArrangementProperties` and `Tones`.
- `Tone2014` provides `GearList`, `ToneDescriptors`, `Key`, and `Name`.
- `Gear2014` defines Amp, Cabinet, four pre-pedal, four post-pedal, and four rack slots.
- `Pedal2014` serializes the Rocksmith device key as `Key` and exposes `KnobValues`.

## Decision

Add a conservative Python adapter for the supported Rocksmith 2014 song-manifest shape.

The adapter:

1. Reads only the nested `Entries` structure used by `Manifest2014<Attributes2014>`.
2. Ignores vocal arrangements.
3. Resolves Lead/Rhythm/Bass primarily from `ArrangementProperties.PathLead`, `PathRhythm`, and `PathBass`; arrangement-name text is only a fallback.
4. Requires explicit artist, song title, tone key, and at least one valid gear component before emitting a reference.
5. Preserves only numeric knob values and never coerces arbitrary strings or booleans into settings.
6. Emits no tone-change timestamps from manifest data alone. Tone changes require separate arrangement/SNG evidence and will be added by a later adapter.
7. Accepts source authority (`official_rocksmith`, `custom_dlc`, etc.) from the caller rather than inferring official status from a single manifest field.
8. Uses synthetic fixtures in repository tests. No extracted commercial manifests are committed.

## Consequences

The reference library can now receive normalized static tone definitions from a known manifest schema without silently fabricating data. Some valid packages with unusual or unsupported shapes will initially produce no records; that is preferable to contaminating the empirical tone corpus with guessed mappings.

A later integration step will bind this parser to verified extraction receipts, add package classification using multiple signals, and recover tone-change timing from authoritative arrangement data.