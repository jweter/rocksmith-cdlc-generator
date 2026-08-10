# ADR-008: Unified validation gate and review queue

## Status

Accepted for Milestone 6.

## Context

Earlier stages emitted stage-specific review artifacts for beat tracking, bass transcription, and fret mapping. The roadmap requires a project-level PASS/WARNING/FAIL gate before authoring export or packaging, plus a concise human review queue so uncertain moments are surfaced rather than buried in large machine outputs.

## Decision

Add a deterministic `cdlc validate PROJECT` stage that reads the canonical project manifest plus current tempo, transcription, and mapped-bass artifacts.

The validator checks at minimum:

- required artifact presence;
- beat and note positions against source-audio duration;
- low-confidence beat events;
- monophonic bass overlaps;
- unresolved/low-confidence transcription notes;
- unmapped notes;
- string/fret pitch consistency with the selected tuning;
- configured maximum fret limits;
- unresolved mapping-confidence flags.

Every finding becomes a structured review item with a stable code, severity, stage, optional song timestamp/note index, and priority. The project status is `FAIL` if any hard failure exists, otherwise `WARNING` when review items remain, otherwise `PASS`.

`FAIL` sets `can_package=false`. Future EOF/DLC Builder integrations must consume this gate and refuse to package a failing project.

## Outputs

- `review/validation_report.json`: complete validation state and queue;
- `review/flags.json`: machine-oriented ordered review items;
- `review/summary.md`: compact human-readable review list.

## Consequences

Validation remains deterministic and independent from LLM judgment. Human review is focused on specific timestamps and note indices, while downstream exporters get a single authoritative packaging decision instead of interpreting several stage-specific files independently.
