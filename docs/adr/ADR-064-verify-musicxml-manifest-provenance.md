# ADR-064: Verify MusicXML Manifest Provenance Before Publication

## Status

Accepted

## Context

ADR-063 introduced a durable project-level manifest that binds human-selected MusicXML parts to normalized Lead, Rhythm, and Bass arrangement outputs. The source score remains outside the project and can therefore be edited or re-exported while an import is running.

If the source changes after initial inspection but before manifest publication, an imported arrangement can carry provenance from different bytes than the inspection metadata recorded by the manifest. A preview/editor must not trust such a mixed-state manifest.

## Decision

1. Treat the initial MusicXML inspection SHA-256 as the authority for one multi-arrangement import transaction.
2. After each normalized arrangement is written, read it back and require its source filename and SHA-256 to match the inspection.
3. Require the normalized track to match the explicitly selected source part index and arrangement role.
4. Re-hash the MusicXML source immediately before writing the durable arrangement manifest.
5. If any provenance or selection check fails, fail closed and do not publish the manifest.
6. Partial normalized arrangement files may remain as private project artifacts, but without a manifest they are not an authoritative project-level arrangement set.

## Consequences

The Song Preview & Timing Editor can treat a published MusicXML arrangement manifest as an internally consistent snapshot of one inspected source version. Source edits during import are detected instead of silently producing mixed provenance.
