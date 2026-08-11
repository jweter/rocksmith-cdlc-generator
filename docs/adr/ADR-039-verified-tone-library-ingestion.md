# ADR-039: Verified tone-library ingestion

## Status

Accepted.

## Context

The project can now (1) create SHA-256-verified private copies of installed Rocksmith `.psarc` files, (2) extract those copies into an ignored private workspace, and (3) conservatively parse supported Rocksmith 2014 manifest tone structures. Those steps must be connected without weakening the live-install boundary or allowing broad candidate discovery to become speculative data.

## Decision

Add a single ingestion pipeline that accepts only a matching verified-copy/extraction pair and then:

1. verifies the extraction SHA-256 and private-copy path against the staging receipt;
2. accepts tone JSON candidates only when they resolve beneath the recorded private extraction directory;
3. parses supported manifest structures conservatively and ignores malformed or unsupported candidate JSON;
4. records the original installed PSARC path and hash as provenance rather than treating the private copy as the source package;
5. requires the caller to supply `official_rocksmith`, `custom_dlc`, `user_created`, or `unknown` explicitly rather than guessing authority from filenames or ambiguous package fields;
6. merges the resulting references through the existing incremental local tone-library model; and
7. writes only the derived library artifact to caller-selected private/ignored storage.

The live Rocksmith installation remains immutable. Extraction and parsing operate only on the verified private copy. The only direct access to the installed PSARC in this workflow is the read-only staging/hash operation and the metadata/hash read used by the existing library merge routine.

## Consequences

A locally installed DLC package can now move deterministically from live read-only source to verified private copy to normalized tone records without manual handoff between subsystems. Authority remains explicit and auditable. Unsupported manifests produce zero records instead of guessed tones.

This ADR does not authorize redistribution of extracted manifests, DLC, audio, or Ubisoft-derived assets. Generated library artifacts remain private and ignored by version control.

## Next

Build a batch scanner around `changed_psarcs()` so the user's large local DLC collection can be incrementally staged and indexed, with per-package failures isolated and summarized rather than aborting the whole scan.
