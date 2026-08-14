# Local source rights review

`cdlc-sources PROJECT` reports every known local source by SHA-256 and keeps sources with `rights_class: unknown` in the human review queue. Use `cdlc-source-rights` after a human has verified how a local file was obtained.

```text
cdlc-sources projects/artist-song
cdlc-source-rights projects/artist-song <SOURCE_SHA256> --rights-class user_owned_local --note "Owned DRM-free local copy"
cdlc-sources projects/artist-song
```

Accepted reviewed classes are `user_owned_local`, `licensed_download`, `creative_commons`, `public_domain`, and `self_recorded`. `unknown` cannot be confirmed, and `streaming_reference_only` is deliberately excluded because streaming/video references never represent local ingest bytes.

Reviews are append-only JSON records under `sources/intake/rights_reviews/`. They are keyed to the immutable source SHA-256 rather than a filename, so renaming or moving the original file does not change which source was reviewed. A later review supersedes the earlier review for current readiness while preserving the full audit history.

The original intake receipt and `project.json` are never rewritten. `cdlc-sources` overlays the latest human review onto its effective readiness view and exposes the review record path and timestamp. This also gives older projects created through `cdlc new` a durable way to resolve their legacy `unknown` rights state.

A rights review is provenance metadata only. It does **not** make the file trusted musical ground truth, does not approve uncertain transcription/fingering/tone decisions, does not authorize redistribution, and does not bypass any validation or human musical-review gate.
