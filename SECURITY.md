# Security Policy

## Supported code

Security fixes are made against the current `main` branch. Older snapshots, local modifications, third-party tools, and generated Rocksmith/CDLC artifacts are not maintained as separately supported releases.

## Reporting a vulnerability

Please do not open a public issue for a vulnerability that could enable code execution, credential exposure, unsafe file access, destructive behavior, path traversal, malicious package handling, or another exploitable condition.

Instead, use GitHub's private vulnerability reporting feature when it is available for this repository. If private reporting is unavailable, contact the repository owner privately through GitHub before publishing technical details.

Include enough information to reproduce and assess the problem:

- affected commit, branch, or packaged build;
- affected operating system and relevant dependency versions;
- reproduction steps or a minimal proof of concept;
- expected versus observed behavior;
- security impact;
- whether untrusted audio, score, archive, PSARC, path, metadata, or other input is involved.

Please avoid including copyrighted song audio, private Rocksmith profile data, credentials, tokens, or other sensitive material in the report.

## Security boundaries

The project is designed to be local-first and fail closed around authoring and packaging state. Security reports are especially relevant when behavior crosses any of these boundaries:

- modifying files outside the selected project workspace;
- changing the live Rocksmith installation or player profile without explicit user action;
- bypassing validation, provenance, source-rights, review, or packaging gates;
- executing commands derived from untrusted external content;
- exposing credentials or private local data;
- unsafe extraction or processing of archives, PSARC files, score files, or media;
- downloading or executing unverified third-party binaries or models.

## Disclosure

Please allow reasonable time for triage and remediation before public disclosure. Confirmed vulnerabilities should receive a focused fix, regression coverage where practical, and documentation of the root cause.
