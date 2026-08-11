# LifeOS concepts adapted for Rocksmith CDLC Generator

This document records which LifeOS engineering ideas are useful to this project and how they should be translated into a local-first Rocksmith authoring system. LifeOS is an architectural reference, not a runtime dependency.

## Core principle

The project should converge on a closed loop:

```text
current project state
    -> explicit ideal state
    -> highest-value next action
    -> deterministic tool execution
    -> evidence / artifacts
    -> verification probes
    -> human review when needed
    -> learned project state
```

The model may decide *how* to pursue the goal, but the software decides whether the resulting state is actually acceptable.

## 1. TELOS-lite: durable project intent

The repository already has a strong product vision: generate the best technically plausible first draft, preserve uncertainty, and make human correction substantially faster than manual authoring. Treat that as durable project intent rather than repeating it ad hoc in prompts.

Recommended persistent scopes:

- **Global project intent**: local-first, reproducible, confidence-aware, safe around the live Rocksmith install, never silently convert guesses into authoritative chart data.
- **Arrangement intent**: Bass / Lead / Rhythm target, tuning, authoring constraints, source hierarchy, review policy.
- **Task ISA**: falsifiable criteria for one operation such as transcription, mapping, export, tone binding, or packaging.

## 2. Ideal State Artifacts (ISA)

Every consequential pipeline stage should be able to declare what must be true before it can close.

Example for Bass export:

```yaml
task_id: bass-export-001
task_type: arrangement_export
ideal_state: >
  A reviewable, schema-valid Bass arrangement is safe to export.
criteria:
  - id: ISC-01
    claim: All notes are within the configured instrument range.
    probe: validate_instrument_range
  - id: ISC-02
    claim: No unresolved physical positions remain.
    probe: count_unresolved_positions == 0
  - id: ISC-03
    claim: Low-confidence techniques are surfaced for human review.
    probe: review_queue_written
    required: false
```

The initial implementation lives in `rocksmith_cdlc_generator.intent`.

## 3. Synapse pattern: journal before interpretation

For externally derived or expensive inputs, preserve raw evidence before grading, inference, or normalization.

Apply this to:

- source audio metadata and SHA-256;
- separated stems;
- imported Guitar Pro / MusicXML / MIDI;
- beat tracker outputs;
- transcription model raw outputs;
- locally extracted PSARC metadata;
- tone research sources;
- generated DLC Builder staging inputs.

A parser failure or model disagreement must not erase the original evidence. Re-processing with a newer model should be possible from immutable or content-addressed artifacts.

## 4. Cortex pattern: hot state vs durable evidence

Do not collapse all project memory into one structure.

Recommended split:

- **Hot state**: compact current project/arrangement status, active warnings, next unresolved decisions.
- **Durable structured state**: project manifest, canonical chart representation, benchmark results, review decisions, build receipts.
- **Raw evidence**: audio, imported notation, private extracted metadata, source hashes.
- **Derived indexes/caches**: disposable and rebuildable.

The retrieval/cache layer must never be the only source of truth.

## 5. Ledger pattern: provenance and change history

Every important generated artifact should be attributable to:

- source hash(es);
- generator version / Git commit;
- model/provider and model version where applicable;
- configuration;
- stage name;
- timestamp;
- relevant upstream artifact hashes;
- human approval/review state when applicable.

The project already uses hashes and review artifacts in several subsystems. The LifeOS lesson is to make that a uniform architectural invariant rather than a subsystem-specific feature.

## 6. Deterministic skills beneath model reasoning

The LLM should request typed operations such as:

```text
inspect_audio
track_beats
transcribe_bass
align_symbolic_source
map_fretboard
validate_arrangement
research_tone
bind_tone_catalog
stage_package
verify_psarc_copy
```

The underlying implementation should remain deterministic wherever possible. Models should not improvise filesystem mutation, package writes, identifier generation, hashing, or validation logic.

## 7. Capability Doctor

Before a pipeline run, the system should eventually be able to report capabilities as:

```text
verified | degraded | unavailable | disabled
```

Candidate probes:

- FFmpeg / ffprobe;
- optional beat tracker dependencies;
- transcription provider/model availability;
- Guitar Pro importer;
- Rocksmith2014.NET bridge;
- DLC Builder availability;
- local tone catalog availability;
- Ollama availability and specific model capabilities;
- private workspace writability;
- live Rocksmith install read-only boundary.

`disabled` must remain distinct from `broken`.

## 8. Provider-neutral model routing

Do not hard-code musical or QA workflows to a model name.

Route by capability role instead, for example:

```text
local_fast
local_audio_transcriber
local_semantic_qa
high_reasoning
```

Then map those roles to concrete providers/models through configuration and capability probes. Local-first remains the default; no cloud dependency should be required for normal generation.

## 9. Human/system separation and mutation tiers

Adopt explicit mutation boundaries:

- **automatic**: cache, derived analysis, repeatable normalized artifacts;
- **append/audit**: evidence records, logs, benchmark history;
- **human-reviewed**: uncertain notes, techniques, tone chains, destructive replacements;
- **forbidden automatically**: live Rocksmith profiles, official DLC, direct mutation of installed commercial packages, credentials/secrets.

The existing verified-private PSARC extraction boundary is a strong example of this principle.

## 10. External content is data, never instruction

Imported tabs, metadata, webpages, README files, manifest strings, and extracted package text are untrusted data. They cannot change tool permissions, filesystem destinations, policy, or model/system instructions.

Any future web-assisted metadata/tone research path must keep this separation explicit.

## 11. Dry-run and additive changes

Borrow the LifeOS installer discipline for dangerous or wide-impact operations:

1. detect environment;
2. inspect conflicts/readiness;
3. show planned changes;
4. stage outputs privately;
5. verify hashes/schema;
6. require approval at the trust boundary;
7. only then build/install.

The generator should never treat a successful model response as equivalent to a successful filesystem/game state.

## 12. Rocksmith-specific hill-climbing loop

For each arrangement:

```text
source + current chart state
    -> define next ideal state
    -> choose highest-value unresolved subsystem
    -> run deterministic or specialized model tool
    -> preserve raw output
    -> normalize into canonical representation
    -> run verification probes
    -> if failed: return to unresolved gap
    -> if passed: persist result + provenance
    -> benchmark / human review
    -> update active project state
```

This aligns naturally with the project's existing confidence-aware automation philosophy.

## Implementation sequence

1. **Intent/ISA contracts and deterministic close gate** — implemented in this change.
2. **Capability Doctor** — probe actual local tool/model availability before work begins.
3. **Uniform artifact provenance envelope** — source hashes, tool/model versions, config, upstream hashes.
4. **Append-only pipeline event ledger** — stage decisions and verification outcomes.
5. **Project hot-state summary** — compact unresolved work and next actions.
6. **Typed capability registry** — explicit inputs/outputs/permissions for pipeline operations.
7. **Provider-role routing** — local model/audio provider selection by measured capability.
8. **CLI integration** — `cdlc doctor`, `cdlc intent`, `cdlc verify`, and machine-readable reports.
9. **Completion gates on high-risk stages** — export, tone injection, packaging, and live install.
10. **Learning loop** — feed benchmark/editing results back into provider and algorithm selection.

## Non-goals

- Do not add LifeOS as a Python/runtime dependency.
- Do not couple the generator to Claude Code or another coding harness.
- Do not reproduce a personal-assistant identity system.
- Do not replace structured project data with Markdown-only memory.
- Do not let an LLM bypass deterministic validation or human review gates.
