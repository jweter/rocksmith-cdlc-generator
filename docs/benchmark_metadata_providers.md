# Benchmark metadata providers

Issue #46 introduces catalog metadata enrichment as an optional layer. The core package now exposes a provider-neutral contract in `rocksmith_cdlc_generator.benchmark_metadata`.

Providers may return redistributable descriptive fields such as canonical artist/title, album, duration, release date, ISRC, provider track ID, and a public source-page URL. Provider implementations must not return or persist commercial audio, authentication secrets, local media paths, private CFSM exports, Ubisoft-derived content, or any other source bytes.

`enrich_benchmark_metadata()` always wraps a successful lookup in a receipt with `human_review_required=true`. Catalog metadata can improve candidate identity and duration accuracy, but it does not establish musical ground truth, structured-reference acceptance, tone decisions, or benchmark promotion by itself.

`rocksmith_cdlc_generator.apple_music_metadata.AppleMusicMetadataProvider` implements the contract using Apple's public, unauthenticated `itunes.apple.com/search` endpoint -- no Apple Developer account, MusicKit token, or other paid/credentialed access. It matches results by normalized artist/title equality and returns `None` when no result matches both fields, rather than guessing. The endpoint does not expose ISRC, so `isrc` is always left unset by this provider instead of being fabricated. It is intentionally not a runtime or build dependency of the core package, and an unavailable provider or no-confident-match result is a normal non-error outcome.
