# ADR-018: Licensed audio provider acquisition boundary

## Status

Accepted for Milestone 8.5.

## Context

The generator benefits from legal, reproducible audio sources for testing and from user-authorized provider downloads. Provider APIs expose several different facts that must not be conflated:

1. whether the provider permits an application to download a track;
2. which license or rights metadata the provider reports for that track;
3. whether a derivative/custom Rocksmith package may be redistributed.

Those are separate questions. A provider-level download flag does not by itself establish downstream redistribution rights.

## Decision

Provider audio acquisition is an optional pre-project workflow:

```text
provider search -> cached candidate report -> explicit candidate selection/download
                -> local audio + provenance sidecar -> normal `cdlc new --audio ...`
```

The core project constructor remains local-file based.

The first adapter is Jamendo API v3. The adapter:

- requires a Jamendo developer client id, preferably through `JAMENDO_CLIENT_ID`;
- uses the provider's `audiodownload_allowed` field as the gate for application download;
- never substitutes the streaming `audio` URL for a disallowed download;
- records the provider track id, license URL, selected candidate index, local SHA-256, byte size, and retrieval time;
- sets `redistribution_rights_review_required=true` on every acquisition receipt;
- rejects non-HTTPS download URLs.

The tool does not claim that a provider-authorized download is automatically safe to redistribute as CDLC.

## Jamendo compatibility basis

Jamendo API v3 documents that all API requests require a `client_id`. Its tracks APIs expose `audiodownload_allowed`, and its tracks/file endpoint returns a file only where download is allowed. Track records also expose Creative Commons license URLs.

## Consequences

- Legal/source provenance stays attached to acquired audio.
- Provider credentials do not become project-format dependencies.
- Additional lawful providers can implement the same search/report/download boundary later.
- Local user-owned audio remains the primary ingestion path.
- CI tests use injected provider responses and synthetic bytes; no third-party music is downloaded in tests or committed to the repository.
