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

Multiple intake or score-registration receipts may refer to the same immutable source bytes. Rights readiness is therefore consolidated by SHA-256 before workflow gates are evaluated. If any receipt for that content still requires review, or if individually resolved receipts disagree on `rights_class`, the authoritative inventory marks every receipt for that SHA as `human_rights_review_required: true` with an effective `rights_class: unknown`. `unresolved_rights_reviews` counts that content once. The source-rights workflow step, guided UI, and score fan-out all remain blocked until a single explicit human review resolves the content-level state.

This fail-closed consolidation is part of the authoritative workflow model, not merely presentation logic. Deterministic automation must never continue across conflicting source-rights classifications, even when each individual receipt would otherwise look resolved in isolation.

A rights review is provenance metadata only. It does **not** make the file trusted musical ground truth, does not approve uncertain transcription/fingering/tone decisions, does not authorize redistribution, and does not bypass any validation or human musical-review gate.
