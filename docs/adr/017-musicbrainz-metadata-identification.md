# ADR-017: MusicBrainz metadata identification is optional, cached evidence

## Status

Accepted for Milestone 8.5.

## Context

Imported notation and audio files often have incomplete or inconsistent song metadata. Metadata is useful for DLC Builder project preparation, naming, album/year review, and source provenance, but a live network lookup must not become part of the deterministic packaging path.

MusicBrainz provides a public Web Service v2 API with recording search, JSON responses, no API key for ordinary read access, a required meaningful User-Agent, and published rate-limit expectations. Search results are evidence candidates rather than authoritative truth for the exact local recording.

## Decision

1. MusicBrainz is an optional metadata-identification provider.
2. Queries use the project's existing artist/title and use local audio duration only as secondary ranking evidence.
3. Provider score and local duration agreement remain separate inputs to a normalized candidate confidence.
4. Every lookup is persisted as a project-local JSON snapshot beneath `metadata/` with query inputs, request URL, retrieval timestamp, provider IDs, scores, and normalized candidates.
5. A cached artifact is reused without a network request unless refresh is explicitly requested.
6. Provider results do not overwrite `project.json` automatically.
7. Candidate selection is an explicit action that writes `metadata/selected.json`, preserving the source report and selected index.
8. Packaging and validation must remain usable without MusicBrainz availability.
9. Provider metadata confidence is not note/transcription confidence and must never promote symbolic musical evidence.

## Consequences

- Builds remain reproducible and offline after enrichment.
- A user can inspect why a title/artist/release was suggested.
- Wrong MusicBrainz matches cannot silently mutate the canonical project manifest.
- Future providers can implement the same candidate/snapshot/selection contract.
- Commercial deployment must separately review MusicBrainz service terms rather than assuming the free non-commercial Web Service policy applies.

## Follow-up

- Expose identification and candidate selection through the main `cdlc` CLI.
- Teach DLC Builder preparation to optionally read reviewed `metadata/selected.json` for suggested album/year values while preserving explicit override behavior.
- Add licensed/public-domain audio provider adapters under a separate provenance contract; metadata lookup alone does not imply audio download rights.
