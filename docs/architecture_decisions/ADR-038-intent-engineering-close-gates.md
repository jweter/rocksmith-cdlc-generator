# ADR-038: Intent-engineering contracts and deterministic close gates

## Status

Accepted for initial implementation.

## Context

The generator has multiple stages where plausible-looking output is not enough to prove that the pipeline state is safe or complete. Examples include transcription, physical fret/string mapping, arrangement export, tone binding, PSARC staging, and future package installation.

The project's existing design already favors confidence-aware automation, explicit human review, provenance, validation, and preservation of the live Rocksmith installation. LifeOS contributes a useful generalization: define an explicit task-specific ideal state and evaluate it with evidence-bearing probes rather than allowing a model or orchestration layer to declare success from narrative confidence.

## Decision

Introduce a provider-neutral task intent contract containing:

- current state;
- ideal state;
- constraints;
- unique falsifiable criteria;
- named verification probes;
- required vs optional criteria.

Introduce deterministic probe results and a close gate. A task cannot close when a required criterion fails, is not run, or has no result. Warnings are surfaced without being silently promoted to failures or successes. Unknown and duplicate criterion results are rejected.

The first implementation is `rocksmith_cdlc_generator.intent`.

LifeOS remains an architectural reference only. This repository will not depend on the LifeOS runtime, Claude Code lifecycle hooks, or LifeOS filesystem layout.

## Alternatives

### Continue with subsystem-specific booleans and ad hoc validation

Rejected as the long-term architecture because completion semantics become fragmented and difficult to audit across stages.

### Let an LLM decide whether a stage is complete

Rejected. Narrative assessment is not evidence that Rocksmith XML, fret positions, package hashes, or safety constraints are correct.

### Depend directly on LifeOS

Rejected because the CDLC generator is a local-first Python application and should remain independent of any coding-agent harness or model provider.

## Consequences

Positive:

- completion criteria become explicit and testable;
- stage gates can be audited and serialized;
- high-risk workflows can share one verification pattern;
- models retain flexibility in execution without owning the definition of success;
- future CLI/UI surfaces can explain exactly why a task is blocked.

Costs:

- each high-value pipeline stage must define meaningful criteria and probes;
- probe quality becomes part of system quality;
- some existing validators will eventually need adapters into the common result model.

## Follow-up

- add capability Doctor probes;
- define a common provenance envelope;
- add an append-only pipeline event ledger;
- integrate intent/verification with arrangement export and package staging first;
- expose machine-readable close-gate reports through the CLI.
