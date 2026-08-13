# Structured-reference research records

Issue #45 requires the 20-song benchmark candidate bank to be checked against lawful structured-reference sources before any candidate can be promoted.

`rocksmith_cdlc_generator.benchmark_source_research.BenchmarkSourceResearchRecord` is the metadata-only record for that research step. It records one of five outcomes: official/commercial Guitar Pro, community Guitar Pro, other structured notation, no adequate source found, or not checked.

When a structured source is found, the record requires an HTTP(S) source-page URL and a human-readable source title so the research result is auditable without storing copyrighted notation. Local filesystem locations and source bytes are intentionally outside the model. Unknown fields are forbidden.

These research records are **not** benchmark provenance acceptance records. Finding a structured source does not mean it has been acquired lawfully, hashed, reviewed, or accepted as ground truth. Promotion remains blocked until the separate provenance and human-acceptance gates are satisfied.

The next Issue #45 slice should populate research records for the committed 20-song candidate bank from lawful public source metadata only. Copyrighted Guitar Pro/MIDI/MusicXML/CDLC files remain outside Git.
